import { useEffect, useState, type ReactNode } from "react";
import {
  Alert, Badge, Box, Button, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, Divider, LinearProgress, MenuItem, Paper, Stack, Table,
  TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, date, money, post, quantity } from "./api";
import { useApp } from "./context";
import type { Order } from "./types";
import OrderPaymentPanel from "./OrderPayment";

type DeliveryRow = {
  id: number; number: string; branch_id: number; branch_name: string;
  customer_name: string; customer_phone: string; address: string;
  driver_id: number | null; driver_name: string | null; status: string;
  delivery_state: string; delivery_state_label: string; payment_status: string;
  total: string; created_at: string; assigned_at: string | null;
  started_at: string | null; completed_at: string | null; trip_minutes: number | null;
  failed_attempts: number; last_issue: string; can_assign: boolean;
  destination_latitude: string | null; destination_longitude: string | null;
};
type Driver = {
  id: number; name: string; branch_id: number; branch_name: string; active: boolean;
  total_assigned: number; assigned: number; in_transit: number; current_workload: number; completed: number;
  unsuccessful: number; failed_attempts: number; cancelled: number; rejected: number;
  expired: number; average_trip_minutes: number | null;
};
type Report = {
  summary: Record<string, number>;
  statuses: { value: string; label: string; count: number }[];
  drivers: Driver[]; orders: DeliveryRow[]; total: number; page: number;
  pages: number; page_size: number; period_basis: string;
};
type Detail = Order & DeliveryRow & {
  history: { id: number; status: string; note: string; created_at: string; actor_name: string; actor_role: string }[];
  available_drivers: { id: number; name: string; current_workload: number }[];
};
type Column<T> = { label: string; value: (row: T) => ReactNode };
function DeliveryTable<T>({ rows, columns }: { rows: T[]; columns: Column<T>[] }) {
  return <TableContainer component={Paper} variant="outlined"><Table size="small" sx={{ minWidth: 700 }}>
    <TableHead><TableRow>{columns.map(column => <TableCell key={column.label} sx={{ whiteSpace: "nowrap" }}>{column.label}</TableCell>)}</TableRow></TableHead>
    <TableBody>{rows.map((row, index) => <TableRow key={index} hover>{columns.map(column => <TableCell key={column.label}>{column.value(row)}</TableCell>)}</TableRow>)}
      {!rows.length && <TableRow><TableCell colSpan={columns.length} sx={{ py: 4, textAlign: "center" }}>No matching records.</TableCell></TableRow>}
    </TableBody>
  </Table></TableContainer>;
}
const statusColors: Record<string, "success" | "error" | "warning" | "primary" | "default"> = {
  completed: "success", unsuccessful: "error", rejected: "error", expired: "warning",
  unassigned: "warning", assigned: "primary", in_transit: "primary", cancelled: "default",
};
function DeliveryStatus({ value, label }: { value: string; label?: string }) {
  return <Chip size="small" variant="outlined" color={statusColors[value] || "default"} label={label || value.replaceAll("_", " ")} />;
}
const when = (value: string | null) => value ? date(value) : "Not recorded";

export default function DeliveryManagement({ branch }: { branch: number }) {
  const { notify } = useApp(), qc = useQueryClient();
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [driver, setDriver] = useState("");
  const [status, setStatus] = useState("all");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number | null>(null);
  const [assignment, setAssignment] = useState("");
  const [saving, setSaving] = useState(false);
  const [assignmentError, setAssignmentError] = useState("");
  useEffect(() => { setDriver(""); setPage(1); setSelected(null); }, [branch]);
  const params = new URLSearchParams({ status, page: String(page) });
  if (branch) params.set("branch_id", String(branch));
  if (driver) params.set("driver_id", driver);
  if (fromDate) params.set("from_date", fromDate);
  if (toDate) params.set("to_date", toDate);
  if (search) params.set("search", search);
  const report = useQuery({
    queryKey: ["delivery-operations", branch, driver, status, fromDate, toDate, search, page],
    queryFn: () => api<Report>(`/delivery/operations?${params}`), refetchInterval: 15000, placeholderData: keepPreviousData,
  });
  const detail = useQuery({
    queryKey: ["delivery-operation-detail", selected], enabled: selected !== null,
    queryFn: () => api<Detail>(`/delivery/operations/${selected}`), refetchInterval: 15000,
  });
  useEffect(() => {
    const assigned = detail.data?.available_drivers.find(person => person.id === detail.data?.driver_id);
    setAssignment(assigned ? String(assigned.id) : "");
    setAssignmentError("");
  }, [selected, detail.data?.driver_id]);
  const data = report.data, order = detail.data;
  function chooseStatus(value: string) { setStatus(value); setPage(1); }
  async function assignTask() {
    if (!order || !assignment || saving) return;
    setSaving(true); setAssignmentError("");
    try {
      await post(`/orders/${order.id}/assign-delivery`, { delivery_user_id: Number(assignment) });
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["delivery-operations"] }),
        qc.invalidateQueries({ queryKey: ["delivery-operation-detail"] }),
        qc.invalidateQueries({ queryKey: ["orders"] }),
      ]);
      notify("Delivery task assigned. It is available in the delivery person's app.");
    } catch (error) { setAssignmentError((error as Error).message); }
    finally { setSaving(false); }
  }
  return <>
    <div className="workspace-heading"><div>
      <span className="eyebrow">CHINNU WORKSPACE</span>
      <Typography variant="h4">Delivery operations & performance</Typography>
      <Typography color="text.secondary" sx={{ mt: 1 }}>Assign delivery tasks, review each person's workload, and follow every order through to its outcome.</Typography>
    </div><Button variant="outlined" onClick={() => void report.refetch()} disabled={report.isFetching}>Refresh</Button></div>

    <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
      <Stack direction={{ xs: "column", md: "row" }} gap={2}>
        <TextField label="Order date from" type="date" value={fromDate} slotProps={{ inputLabel: { shrink: true } }} onChange={e => { setFromDate(e.target.value); setPage(1); }} />
        <TextField label="Order date to" type="date" value={toDate} slotProps={{ inputLabel: { shrink: true } }} onChange={e => { setToDate(e.target.value); setPage(1); }} />
        <TextField select label="Delivery person" value={driver} sx={{ minWidth: { md: 230 } }} onChange={e => { setDriver(e.target.value); setPage(1); }}>
          <MenuItem value="">All delivery people</MenuItem>
          {data?.drivers.map(person => <MenuItem key={person.id} value={String(person.id)}>{person.name}{!branch ? ` · ${person.branch_name}` : ""}{!person.active ? " (inactive)" : ""}</MenuItem>)}
        </TextField>
        <Button onClick={() => { setFromDate(""); setToDate(""); setDriver(""); setSearch(""); setSearchInput(""); setStatus("all"); setPage(1); }}>Reset filters</Button>
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>{data?.period_basis || "All-time delivery report. Choose order dates to review a specific period."}</Typography>
    </Paper>
    {report.isError && <Alert severity="error" sx={{ mb: 2 }}>{report.error.message}</Alert>}
    {report.isFetching && !report.isPending && <LinearProgress sx={{ mb: 2 }} />}
    {report.isPending && <Box sx={{ py: 4, textAlign: "center" }}><CircularProgress /></Box>}
    {data && <>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(3, 1fr)" }, gap: 2, mb: 4 }}>
        {[["all", "Delivery orders"], ["unassigned", "Ready · not assigned"], ["in_transit", "Out for delivery"], ["completed", "Completed"], ["unsuccessful", "Needs attention"], ["failed_attempts", "Failed delivery attempts"]].map(([field, label]) =>
          <Paper variant="outlined" key={field} sx={{ p: 2.5, bgcolor: field === "completed" ? "primary.main" : undefined, color: field === "completed" ? "primary.contrastText" : undefined }}>
            <Typography variant="body2">{label}</Typography><Typography variant="h4" sx={{ mt: 1, fontWeight: 700 }}>{data.summary[field]}</Typography>
          </Paper>)}
      </Box>
      <Typography variant="h6" sx={{ mb: 1 }}>Delivery-person performance</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>Team totals follow the branch and order-date filters. Current workload includes all active assignments. Failed attempts can include orders later completed.</Typography>
      <DeliveryTable rows={data.drivers} columns={[
        { label: "Delivery person", value: person => <><strong>{person.name}</strong><Typography variant="body2" color="text.secondary">{person.branch_name}{!person.active ? " · Inactive" : ""}</Typography></> },
        { label: "Assigned orders", value: person => person.total_assigned },
        { label: "Awaiting dispatch", value: person => person.assigned },
        { label: "Out for delivery", value: person => person.in_transit },
        { label: "Current workload", value: person => <Chip size="small" label={person.current_workload} color={person.current_workload ? "primary" : "default"} /> },
        { label: "Completed", value: person => person.completed },
        { label: "Needs attention", value: person => person.unsuccessful },
        { label: "Failed attempts", value: person => person.failed_attempts },
        { label: "Cancelled", value: person => person.cancelled },
        { label: "Rejected", value: person => person.rejected },
        { label: "Expired", value: person => person.expired },
        { label: "Avg. trip time", value: person => person.average_trip_minutes === null ? "—" : `${person.average_trip_minutes} min` },
        { label: "Action", value: person => <Button onClick={() => { setDriver(String(person.id)); chooseStatus("all"); }}>View jobs</Button> },
      ]} />
      <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>Delivery jobs</Typography>
      <Box component="form" onSubmit={event => { event.preventDefault(); setSearch(searchInput.trim()); setPage(1); }} sx={{ display: "flex", flexWrap: "wrap", gap: 1.5, mb: 2 }}>
        <TextField label="Search order number, customer or mobile" value={searchInput} onChange={event => setSearchInput(event.target.value)} inputProps={{ maxLength: 100 }} sx={{ flex: 1, minWidth: 220 }} />
        <Button type="submit" variant="outlined">Search</Button>
      </Box>
      <Stack direction="row" gap={2} sx={{ flexWrap: "wrap", py: 1, mb: 2 }}>
        {data.statuses.map(item => <Badge key={item.value} badgeContent={item.count} showZero max={9999} sx={{ "& .MuiBadge-badge": { bgcolor: item.value === "completed" ? "success.main" : ["unsuccessful", "rejected"].includes(item.value) ? "error.main" : "primary.main", color: "white", border: "2px solid white", fontWeight: 700 } }}>
          <Chip label={item.label} onClick={() => chooseStatus(item.value)} color={status === item.value ? "primary" : "default"} />
        </Badge>)}
      </Stack>
      <DeliveryTable rows={data.orders} columns={[
        { label: "Order / branch", value: job => <><strong>{job.number}</strong><Typography variant="body2">{job.branch_name}</Typography><Typography variant="caption" color="text.secondary">{date(job.created_at)}</Typography></> },
        { label: "Customer / address", value: job => <Box sx={{ minWidth: 200, maxWidth: 280 }}><strong>{job.customer_name}</strong><Typography variant="body2">{job.customer_phone}</Typography><Typography variant="body2" color="text.secondary">{job.address}</Typography></Box> },
        { label: "Delivery person", value: job => job.driver_name || "Not assigned" },
        { label: "Delivery status", value: job => <DeliveryStatus value={job.delivery_state} label={job.delivery_state_label} /> },
        { label: "Payment / value", value: job => <>{money(job.total)}<Typography variant="body2">{job.payment_status}</Typography></> },
        { label: "Last issue / reason", value: job => <Typography variant="body2" sx={{ minWidth: 150, maxWidth: 260 }} color={job.last_issue ? "error.main" : "text.secondary"}>{job.last_issue || "—"}</Typography> },
        { label: "Action", value: job => <Button onClick={() => setSelected(job.id)}>{job.can_assign ? job.driver_id ? "View / reassign" : "Assign task" : "View details"}</Button> },
      ]} />
      <Stack direction="row" gap={2} alignItems="center" justifyContent="flex-end" sx={{ mt: 2 }}>
        <Typography variant="body2">{data.total} jobs · Page {data.page} of {data.pages}</Typography>
        <Button disabled={data.page <= 1 || report.isFetching} onClick={() => setPage(data.page - 1)}>Previous</Button>
        <Button disabled={data.page >= data.pages || report.isFetching} onClick={() => setPage(data.page + 1)}>Next</Button>
      </Stack>
    </>}

    <Dialog open={selected !== null} onClose={() => !saving && setSelected(null)} fullWidth maxWidth="md">
      <DialogTitle>{order?.number || "Delivery details"}</DialogTitle>
      <DialogContent>
        {detail.isPending && <CircularProgress />}
        {detail.isError && <Alert severity="error">{detail.error.message}</Alert>}
        {order && <Stack spacing={2.5}>
          <Stack direction="row" justifyContent="space-between" flexWrap="wrap" gap={1}><Typography variant="h6">{order.branch_name}</Typography><DeliveryStatus value={order.delivery_state} label={order.delivery_state_label} /></Stack>
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 3 }}>
            <Box><Typography variant="subtitle2">Customer & destination</Typography><Typography>{order.customer_name}</Typography><Typography>{order.customer_phone}</Typography><Typography sx={{ mt: 1 }}>{order.address}</Typography>
              {order.destination_latitude && order.destination_longitude && <Button href={`https://www.google.com/maps/search/?api=1&query=${order.destination_latitude},${order.destination_longitude}`} target="_blank" rel="noopener noreferrer" sx={{ mt: 1 }}>Customer map pin</Button>}
            </Box>
            <Box><Typography variant="subtitle2">Assignment & timing</Typography><Typography>Delivery person: {order.driver_name || "Not assigned"}</Typography><Typography variant="body2">Assigned: {when(order.assigned_at)}</Typography><Typography variant="body2">Started: {when(order.started_at)}</Typography><Typography variant="body2">Completed: {when(order.completed_at)}</Typography><Typography variant="body2">{order.completed_at ? "Trip time" : "Elapsed trip time"}: {order.trip_minutes === null ? "Not started" : `${order.trip_minutes} min`}</Typography><Typography variant="body2">Failed attempts: {order.failed_attempts}</Typography></Box>
          </Box>
          {order.last_issue && <Alert severity={order.delivery_state === "completed" ? "info" : "warning"}><strong>Last recorded issue:</strong> {order.last_issue}</Alert>}
          {order.can_assign ? <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ mb: 1.5 }}>{order.driver_id ? "Reassign delivery task" : "Assign delivery task"}</Typography>
            {order.available_drivers.length ? <Stack direction={{ xs: "column", sm: "row" }} gap={2}>
              <TextField select fullWidth label="Delivery person in this branch" value={assignment} disabled={saving} onChange={event => setAssignment(event.target.value)}>
                {order.available_drivers.map(person => <MenuItem key={person.id} value={String(person.id)}>{person.name} · {person.current_workload} active jobs</MenuItem>)}
              </TextField>
              <Button variant="contained" disabled={saving || !assignment || assignment === String(order.driver_id)} onClick={() => void assignTask()} sx={{ minWidth: 150 }}>{saving ? "Assigning..." : "Assign task"}</Button>
            </Stack> : <Alert severity="warning">No active delivery people in this branch. Create or activate a delivery account in People & access.</Alert>}
            {assignmentError && <Alert severity="error" sx={{ mt: 2 }}>{assignmentError}</Alert>}
          </Paper> : <Alert severity="info">{["in_transit", "unsuccessful"].includes(order.delivery_state) ? "This trip has started. Review the history and contact the delivery person about any issues." : "Tasks can be assigned or reassigned when the order is ready for dispatch."}</Alert>}
          <Divider />
          <Typography variant="h6">Order items & payment</Typography>
          <DeliveryTable rows={order.items} columns={[
            { label: "Item", value: item => item.name },
            { label: "Quantity", value: item => `${quantity(item.quantity)} ${item.unit}` },
            { label: "Line total", value: item => money(item.line_total) },
          ]} />
          <Stack direction="row" justifyContent="space-between" flexWrap="wrap" gap={1}><Typography>Delivery charge: {money(order.delivery_fee)}</Typography><Typography fontWeight={700}>Total: {money(order.total)} · {order.payment_status}</Typography></Stack>
          <OrderPaymentPanel key={order.id} order={order} />
          <Typography variant="h6">Activity & delivery history</Typography>
          <Stack spacing={1.5}>{order.history.length ? order.history.map(event => <Paper variant="outlined" key={event.id} sx={{ p: 2, borderLeft: 4, borderLeftColor: event.status === "delivery_failed" ? "error.main" : "primary.main" }}>
            <Typography fontWeight={700}>{event.status.replaceAll("_", " ")}</Typography>
            <Typography variant="body2" color="text.secondary">{date(event.created_at)} · {event.actor_name} ({event.actor_role})</Typography>
            {event.note && <Typography variant="body2" sx={{ mt: 1 }}>{event.note}</Typography>}
          </Paper>) : <Typography color="text.secondary">No delivery events have been recorded for this older order.</Typography>}</Stack>
        </Stack>}
      </DialogContent>
      <DialogActions><Button disabled={saving} onClick={() => setSelected(null)}>Close</Button></DialogActions>
    </Dialog>
  </>;
}
