from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from ..auth import get_session
from ..models import get_apartment, get_tariffs, get_residents, is_admin_db
from ..forms import TariffForm, ResidentForm
from ..utils.excel_export import export_to_excel
import os

main = Blueprint('main', __name__)


@main.before_request
def load_session():
    token = request.args.get("token") or session.get("token")
    if token:
        sess = get_session(token)
        if sess:
            session["token"] = token
            session["apartment_id"] = sess["apartment_id"]
            session["telegram_id"] = sess["telegram_id"]
        else:
            session.clear()


@main.route("/login")
def login():
    return render_template("login.html")


@main.route("/")
def dashboard():
    if "apartment_id" not in session:
        return redirect(url_for("main.login"))
    apartment_id = session["apartment_id"]
    apartment = get_apartment(apartment_id)
    return render_template("dashboard.html", apartment=apartment)


@main.route("/tariffs")
def tariffs():
    if "apartment_id" not in session:
        return redirect(url_for("main.login"))
    apartment_id = session["apartment_id"]
    tariffs = get_tariffs(apartment_id)
    return render_template("tariffs.html", tariffs=tariffs)


@main.route("/tariff/new", methods=["GET", "POST"])
def new_tariff():
    if "apartment_id" not in session:
        return redirect(url_for("main.login"))
    form = TariffForm()
    if form.validate_on_submit():
        from ..models import upsert_tariff
        upsert_tariff(session["apartment_id"], form.utility_type.data, form.rate.data, form.valid_from.data)
        flash("Тариф сохранён!", "success")
        return redirect(url_for("main.tariffs"))
    return render_template("tariff_form.html", form=form, title="Новый тариф")


@main.route("/residents")
def residents():
    if "apartment_id" not in session:
        return redirect(url_for("main.login"))
    residents = get_residents(session["apartment_id"])
    return render_template("residents.html", residents=residents)


@main.route("/residents/add", methods=["POST"])
def add_resident():
    if "apartment_id" not in session:
        return redirect(url_for("main.login"))
    if not is_admin_db(session["telegram_id"], session["apartment_id"]):
        flash("Недостаточно прав", "error")
        return redirect(url_for("main.residents"))
    form = ResidentForm()
    if form.validate_on_submit():
        from ..models import add_resident
        add_resident(
            session["apartment_id"],
            form.telegram_id.data,
            form.full_name.data,
            form.is_admin.data
        )
        flash("Жилец добавлен", "success")
    return redirect(url_for("main.residents"))


@main.route("/export/excel")
def export_excel():
    if "apartment_id" not in session:
        return redirect(url_for("main.login"))
    filepath = export_to_excel(session["apartment_id"])
    # if not is_admin_db(session["telegram_id"], session["apartment_id"]):
    #     flash("Недостаточно прав", "error")
    #     return redirect(url_for("main.residents"))
    if not is_admin_db(session["telegram_id"], session["apartment_id"]):
        flash("Нет данных для экспорта", "error")
        return redirect(url_for("main.dashboard"))
    return send_file(filepath, as_attachment=True, download_name="export.xlsx")
