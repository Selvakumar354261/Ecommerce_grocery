"""Branch-scoped delivery operations and performance reports.

Report periods are cohorts of orders placed during the selected Indian dates.
Current workload deliberately includes all dates. Failed attempts are events,
not customer cancellations, and may subsequently end in a successful delivery.
"""
from datetime import datetime, time, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import aliased

from .models import Audit, Branch, Order, OrderEvent, User, now
from .security import require, scope
from .services import get_or_404

STATES = {
    'all': 'All deliveries',
    'awaiting_ready': 'Preparing / awaiting approval',
    'unassigned': 'Ready · unassigned',
    'assigned': 'Assigned · awaiting dispatch',
    'in_transit': 'Out for delivery',
    'unsuccessful': 'Needs attention',
    'completed': 'Completed',
    'cancelled': 'Cancelled by customer',
    'rejected': 'Rejected by store',
    'expired': 'Reservation expired',
}
INDIA = timezone(timedelta(hours=5, minutes=30))


def report_branch(db, user, branch_id):
    require(user, ('admin', 'manager'))
    if user.role == 'manager':
        if branch_id is not None:
            scope(user, branch_id, ('admin', 'manager'))
        branch_id = user.branch_id
        if branch_id is None:
            raise HTTPException(403, 'No branch is assigned to this account.')
    if branch_id is not None:
        get_or_404(db, Branch, branch_id)
    return branch_id


def dataset(branch_id=None, from_date=None, to_date=None):
    event = select(
        OrderEvent.order_id,
        func.min(case((OrderEvent.status == 'dispatched', OrderEvent.created_at))).label('started_at'),
        func.max(case((OrderEvent.status == 'completed', OrderEvent.created_at))).label('completed_at'),
        func.max(case((OrderEvent.status == 'dispatched', OrderEvent.id))).label('started_event_id'),
        func.max(case((OrderEvent.status == 'delivery_failed', OrderEvent.id))).label('failed_event_id'),
        func.max(case((OrderEvent.status.in_(('cancelled', 'rejected')), OrderEvent.id))).label('terminal_event_id'),
        func.sum(case((OrderEvent.status == 'delivery_failed', 1), else_=0)).label('failed_attempts'),
    ).group_by(OrderEvent.order_id).subquery()
    customer, driver, terminal_actor = aliased(User), aliased(User), aliased(User)
    failure, terminal = aliased(OrderEvent), aliased(OrderEvent)
    delivery_state = case(
        (or_(Order.status == 'rejected', and_(Order.status == 'cancelled', or_(terminal.status == 'rejected', terminal_actor.role.in_(('admin', 'manager'))))), 'rejected'),
        (and_(Order.status == 'cancelled', terminal.id.is_not(None), terminal.actor_id.is_(None)), 'expired'),
        (Order.status == 'cancelled', 'cancelled'),
        (Order.status == 'completed', 'completed'),
        (and_(Order.status == 'dispatched', event.c.failed_event_id > func.coalesce(event.c.started_event_id, 0)), 'unsuccessful'),
        (Order.status == 'dispatched', 'in_transit'),
        (and_(Order.status == 'ready', Order.assigned_delivery_user_id.is_(None)), 'unassigned'),
        (Order.status == 'ready', 'assigned'),
        else_='awaiting_ready',
    )
    query = select(
        Order.id, Order.branch_id, Branch.name.label('branch_name'),
        customer.name.label('customer_name'), Order.phone.label('customer_phone'),
        Order.address, Order.status, Order.payment_status, Order.total, Order.created_at,
        Order.assigned_delivery_user_id.label('driver_id'), driver.name.label('driver_name'),
        Order.delivery_assigned_at.label('assigned_at'), Order.reserved_active,
        Order.latitude.label('destination_latitude'), Order.longitude.label('destination_longitude'),
        event.c.started_at, event.c.completed_at,
        func.coalesce(event.c.failed_attempts, 0).label('failed_attempts'),
        failure.note.label('last_failure_reason'), failure.created_at.label('last_failure_at'),
        terminal.note.label('closure_reason'), delivery_state.label('delivery_state'),
    ).join(Branch, Branch.id == Order.branch_id).join(customer, customer.id == Order.user_id).outerjoin(
        driver, driver.id == Order.assigned_delivery_user_id
    ).outerjoin(event, event.c.order_id == Order.id).outerjoin(
        failure, failure.id == event.c.failed_event_id
    ).outerjoin(terminal, terminal.id == event.c.terminal_event_id).outerjoin(
        terminal_actor, terminal_actor.id == terminal.actor_id
    ).where(Order.method == 'delivery')
    if branch_id is not None:
        query = query.where(Order.branch_id == branch_id)
    if from_date:
        query = query.where(Order.created_at >= datetime.combine(from_date, time.min, INDIA))
    if to_date:
        query = query.where(Order.created_at <= datetime.combine(to_date, time.max, INDIA))
    return query.subquery()


def counts(db, data, conditions=()):
    result = db.execute(select(
        func.count().label('all'),
        *[func.coalesce(func.sum(case((data.c.delivery_state == state, 1), else_=0)), 0).label(state) for state in STATES if state != 'all'],
        func.coalesce(func.sum(data.c.failed_attempts), 0).label('failed_attempts'),
    ).select_from(data).where(*conditions)).mappings().one()
    return {key: int(value) for key, value in result.items()}


def delivery_row(values):
    result = dict(values)
    result['number'] = f"ORD-{result['id']:06d}"
    result['delivery_state_label'] = STATES[result['delivery_state']]
    reserved = result.pop('reserved_active')
    result['can_assign'] = result['status'] == 'ready' and reserved
    result['last_issue'] = result['closure_reason'] or result['last_failure_reason'] or ''
    started, completed = result['started_at'], result['completed_at']
    result['trip_minutes'] = round(max(0, ((completed or now()) - started).total_seconds()) / 60, 1) if started else None
    for field in ('total', 'destination_latitude', 'destination_longitude'):
        if result[field] is not None:
            result[field] = str(result[field])
    return result


def operations_report(db, user, branch_id=None, driver_id=None, status='all', from_date=None, to_date=None, search='', page=1, page_size=25):
    branch_id = report_branch(db, user, branch_id)
    if from_date and to_date and from_date > to_date:
        raise HTTPException(422, 'The start date must not be after the end date.')
    if status not in STATES:
        raise HTTPException(422, 'Choose a valid delivery status.')
    if driver_id is not None:
        driver = get_or_404(db, User, driver_id)
        if driver.role != 'delivery' or (branch_id is not None and driver.branch_id != branch_id):
            raise HTTPException(404, 'Delivery person not found in this branch.')
    data = dataset(branch_id, from_date, to_date)
    conditions = []
    if driver_id is not None:
        conditions.append(data.c.driver_id == driver_id)
    search = search.strip()
    if search:
        # Match literal input, not SQL wildcard patterns.
        needle = '%' + search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        tests = [data.c.customer_name.ilike(needle, escape='\\'), data.c.customer_phone.ilike(needle, escape='\\')]
        order_id = search.upper().removeprefix('ORD-')
        if order_id.isdigit() and len(order_id) <= 10 and int(order_id) <= 2147483647:
            tests.append(data.c.id == int(order_id))
        conditions.append(or_(*tests))
    summary = counts(db, data, conditions)
    if status != 'all':
        conditions.append(data.c.delivery_state == status)
    total = db.scalar(select(func.count()).select_from(data).where(*conditions))
    pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, pages)
    orders = [delivery_row(value) for value in db.execute(
        select(data).where(*conditions).order_by(data.c.created_at.desc(), data.c.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).mappings()]

    # Performance is based on the entire branch/date cohort, unaffected by table search.
    aggregates = select(
        data.c.driver_id, func.count().label('total_assigned'),
        *[func.sum(case((data.c.delivery_state == state, 1), else_=0)).label(state) for state in STATES if state != 'all'],
        func.sum(data.c.failed_attempts).label('failed_attempts'),
        func.avg(case((and_(data.c.delivery_state == 'completed', data.c.completed_at >= data.c.started_at), func.extract('epoch', data.c.completed_at - data.c.started_at) / 60))).label('average_trip_minutes'),
    ).where(data.c.driver_id.is_not(None)).group_by(data.c.driver_id).subquery()
    workload = select(Order.assigned_delivery_user_id.label('driver_id'), func.count().label('active_jobs')).where(
        Order.method == 'delivery', Order.status.in_(('ready', 'dispatched')),
    ).group_by(Order.assigned_delivery_user_id).subquery()
    staff_query = select(User, Branch.name, aggregates, func.coalesce(workload.c.active_jobs, 0).label('active_jobs')).join(
        Branch, Branch.id == User.branch_id
    ).outerjoin(aggregates, aggregates.c.driver_id == User.id).outerjoin(workload, workload.c.driver_id == User.id).where(
        User.role == 'delivery',
    ).order_by(User.name, User.id)
    if branch_id is not None:
        staff_query = staff_query.where(User.branch_id == branch_id)
    drivers = []
    for value in db.execute(staff_query).mappings():
        person = value['User']
        performance = {state: int(value[state] or 0) for state in STATES if state != 'all'}
        drivers.append({
            'id': person.id, 'name': person.name, 'branch_id': person.branch_id, 'branch_name': value['name'], 'active': person.active,
            **performance, 'total_assigned': int(value['total_assigned'] or 0),
            'failed_attempts': int(value['failed_attempts'] or 0), 'current_workload': int(value['active_jobs']),
            'average_trip_minutes': round(float(value['average_trip_minutes']), 1) if value['average_trip_minutes'] is not None else None,
        })
    return {
        'summary': summary, 'statuses': [{'value': state, 'label': label, 'count': summary[state]} for state, label in STATES.items()],
        'drivers': drivers, 'orders': orders, 'total': total, 'page': page, 'pages': pages, 'page_size': page_size,
        'period_basis': 'Counts use order placement dates in India. Current workload includes active jobs from all dates. Failed attempts are not cancellations and may later be completed.',
    }


def operations_detail(db, user, order):
    scope(user, order.branch_id, ('admin', 'manager'))
    if order.method != 'delivery':
        raise HTTPException(409, 'This order is for shop pickup, not delivery.')
    data = dataset(order.branch_id)
    report = delivery_row(db.execute(select(data).where(data.c.id == order.id)).mappings().one())
    events = db.execute(select(OrderEvent, User.name, User.role).outerjoin(User, User.id == OrderEvent.actor_id).where(
        OrderEvent.order_id == order.id
    ).order_by(OrderEvent.id)).all()
    report['history'] = [{
        'id': event.id, 'status': event.status, 'note': event.note, 'created_at': event.created_at,
        'actor_name': name or 'System', 'actor_role': role or 'system',
    } for event, name, role in events]
    collections = db.execute(select(Audit, User.name, User.role).outerjoin(User, User.id == Audit.actor_id).where(
        Audit.action == 'order.cash_collected', Audit.reference == str(order.id),
    )).all()
    for entry, name, role in collections:
        report['history'].append({
            'id': -entry.id, 'status': 'payment_received',
            'note': f"Cash collection recorded: INR {entry.details.get('amount', str(order.total))}.",
            'created_at': entry.created_at, 'actor_name': name or 'System', 'actor_role': role or 'system',
        })
    report['history'].sort(key=lambda item: (item['created_at'], item['id']))
    workload = select(func.count()).where(
        Order.assigned_delivery_user_id == User.id, Order.method == 'delivery', Order.status.in_(('ready', 'dispatched')),
    ).correlate(User).scalar_subquery()
    report['available_drivers'] = [{
        'id': person.id, 'name': person.name, 'current_workload': active_jobs,
    } for person, active_jobs in db.execute(select(User, workload).where(
        User.role == 'delivery', User.active == True, User.branch_id == order.branch_id,
    ).order_by(User.name)).all()]
    return report
