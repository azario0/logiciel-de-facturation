from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SubmitField, IntegerField
from wtforms.validators import DataRequired
from datetime import datetime
import pdfkit
import io
from itertools import groupby

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://YOURUSERNAME:YOURPASSWORD@localhost/billing_db'
db = SQLAlchemy(app)

WKHTMLTOPDF_PATH = r'/usr/local/bin/wkhtmltopdf' # TO MODIFY DEPENDING ON YOUR OS
config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    billings = db.relationship('Billing', backref='customer', lazy=True, cascade="all, delete-orphan")

class Billing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id', ondelete='CASCADE'), nullable=False)
    items = db.relationship('BillingItem', backref='billing', lazy=True, cascade="all, delete-orphan")

class BillingItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    billing_id = db.Column(db.Integer, db.ForeignKey('billing.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id', ondelete='CASCADE'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    product = db.relationship('Product')

# Forms
class CustomerForm(FlaskForm):
    name = StringField('Customer Name', validators=[DataRequired()])
    submit = SubmitField('Add Customer')

class ProductForm(FlaskForm):
    name = StringField('Product Name', validators=[DataRequired()])
    price = FloatField('Price (DZD)', validators=[DataRequired()])
    submit = SubmitField('Add Product')

class BillingItemForm(FlaskForm):
    product_id = IntegerField('Product ID', validators=[DataRequired()])
    quantity = IntegerField('Quantity', validators=[DataRequired()])
    submit = SubmitField('Add Item')

# Routes
@app.route('/')
def index():
    customers = Customer.query.all()
    return render_template('index.html', customers=customers)

@app.route('/add_customer', methods=['GET', 'POST'])
def add_customer():
    form = CustomerForm()
    if form.validate_on_submit():
        new_customer = Customer(name=form.name.data)
        db.session.add(new_customer)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('add_customer.html', form=form)

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    form = ProductForm()
    if form.validate_on_submit():
        new_product = Product(name=form.name.data, price=form.price.data)
        db.session.add(new_product)
        db.session.commit()
        return redirect(url_for('products'))
    return render_template('add_product.html', form=form)

@app.route('/products')
def products():
    products = Product.query.all()
    return render_template('products.html', products=products)

@app.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('products'))

@app.route('/customer/<int:customer_id>')
def customer_details(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    sorted_billings = sorted(customer.billings, key=lambda x: x.date.date())
    grouped_billings = groupby(sorted_billings, key=lambda x: x.date.date())
    return render_template('customer_details.html', customer=customer, grouped_billings=grouped_billings)

@app.route('/delete_customer/<int:customer_id>', methods=['POST'])
def delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    db.session.delete(customer)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/add_billing/<int:customer_id>', methods=['GET', 'POST'])
def add_billing(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    form = BillingItemForm()
    products = Product.query.all()
    
    if form.validate_on_submit():
        billing = Billing(customer_id=customer.id)
        db.session.add(billing)
        db.session.commit()
        
        item = BillingItem(billing_id=billing.id, product_id=form.product_id.data, quantity=form.quantity.data)
        db.session.add(item)
        db.session.commit()
        
        return redirect(url_for('customer_details', customer_id=customer.id))
    
    return render_template('add_billing.html', form=form, customer=customer, products=products)

@app.route('/generate_pdf/<int:customer_id>')
def generate_pdf(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    sorted_billings = sorted(customer.billings, key=lambda x: x.date.date())
    grouped_billings = groupby(sorted_billings, key=lambda x: x.date.date())
    html = render_template('pdf_template.html', customer=customer, grouped_billings=grouped_billings)
    pdf = pdfkit.from_string(html, False, configuration=config)
    return send_file(
        io.BytesIO(pdf),
        as_attachment=True,
        download_name=f'{customer.name}_billing.pdf',
        mimetype='application/pdf'
    )

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)