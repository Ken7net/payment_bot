from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, DateField, SelectField, SubmitField, BooleanField
from wtforms.validators import DataRequired, NumberRange

UTILITY_CHOICES = [
    ("electricity", "Электричество"),
    ("water_cold", "Холодная вода"),
    ("water_hot", "Горячая вода"),
    ("gas", "Газ"),
]


class TariffForm(FlaskForm):
    utility_type = SelectField("Ресурс", choices=UTILITY_CHOICES, validators=[DataRequired()])
    rate = FloatField("Тариф (руб)", validators=[DataRequired(), NumberRange(min=0)])
    valid_from = DateField("Действует с", validators=[DataRequired()])
    submit = SubmitField("Сохранить")


class ResidentForm(FlaskForm):
    telegram_id = StringField("Telegram ID", validators=[DataRequired()])
    full_name = StringField("Имя", validators=[DataRequired()])
    is_admin = BooleanField("Админ")
    submit = SubmitField("Добавить")
