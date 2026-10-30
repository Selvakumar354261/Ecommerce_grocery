import logging
import time
from .db import SessionLocal
from .services import expire_reservations

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
log=logging.getLogger('chinnu.worker')

def main():
    log.info('Reservation worker started')
    while True:
        try:
            with SessionLocal.begin() as db:
                count=expire_reservations(db)
            if count:log.info('Released %s expired reservations',count)
        except Exception:
            log.exception('Reservation sweep failed; will retry')
        time.sleep(15)

if __name__=='__main__':main()
