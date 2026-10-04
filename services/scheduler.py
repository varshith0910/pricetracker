from apscheduler.schedulers.background import BackgroundScheduler

from services.price_checker import check_all_products


scheduler = BackgroundScheduler()


def start_scheduler():

    scheduler.add_job(
        check_all_products,
        "interval",
        hours=6,
        id="price_checker",
        replace_existing=True
    )

    scheduler.start()

    print("Price checker scheduler started")


def stop_scheduler():

    scheduler.shutdown()

    print("Price checker scheduler stopped")