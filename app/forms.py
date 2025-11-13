from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, HiddenField, BooleanField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional
from flask_wtf.file import FileField, FileAllowed


class TipForm(FlaskForm):
    restaurant_id = HiddenField(validators=[DataRequired()])
    staff_id = HiddenField(validators=[Optional()])
    amount_cents = IntegerField(validators=[DataRequired(), NumberRange(min=100, max=50000)])
    method_ui = SelectField(choices=[("apple_pay", "Apple Pay"), ("google_pay", "Google Pay"), ("paypal", "PayPal")], validators=[DataRequired()])
    submit = SubmitField("Dar propina")


class ReviewForm(FlaskForm):
    rating = IntegerField(validators=[DataRequired(), NumberRange(min=1, max=5)])
    comment = TextAreaField(validators=[Optional(), Length(max=500)])
    share_allowed = BooleanField()
    photo = FileField(validators=[Optional(), FileAllowed(["jpg", "jpeg", "png"], "Solo jpg/png")])
    submit = SubmitField("Enviar feedback")


class RegisterForm(FlaskForm):
    email = StringField(validators=[DataRequired(), Email()])
    password = PasswordField(validators=[DataRequired(), Length(min=6)])
    name = StringField(validators=[DataRequired(), Length(min=2, max=120)])
    submit = SubmitField("Crear cuenta")


class LoginForm(FlaskForm):
    email = StringField(validators=[DataRequired(), Email()])
    password = PasswordField(validators=[DataRequired()])
    submit = SubmitField("Entrar")
