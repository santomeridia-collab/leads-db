from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from db import get_db_cursor, connection_pool
from auth import auth_bp, login_manager
import os
import re
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import atexit

# Load environment variables
load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv('SECRET_KEY', 'your-strong-secret-key-here-change-in-production')

# Setup Flask-Login
login_manager.init_app(app)
login_manager.login_view = 'auth.login'   # where to redirect if not logged in

# Register the authentication blueprint
app.register_blueprint(auth_bp)

# Setup logging
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)


def validate_form_data(data):
    """Validate all form data"""
    errors = []
    validated = {}
    
    # Field validation rules
    rules = {
        'business_name': {'required': True, 'type': str, 'max': 255},
        'city': {'required': True, 'type': str, 'max': 100},
        'category_type': {'required': True, 'type': str, 'max': 100},
        'address': {'required': False, 'type': str, 'max': 500},
        'contact_number': {'required': True, 'type': str, 'max': 500, 'message': 'Contact number is required'},#'contact_number': {'required': True, 'type': str, 'pattern': r'^[\d\+\-\s]{10,15}$', 'message': 'Please enter a valid contact number (10-15 digits)'},
        'whatsapp': {'required': False, 'type': str, 'pattern': r'^[\d\+\-\s]{10,15}$', 'message': 'Please enter a valid WhatsApp number'},
        'email': {'required': False, 'type': str, 'pattern': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', 'message': 'Please enter a valid email address'},
        'website': {'required': False, 'type': str, 'max': 255},
        'instagram': {'required': False, 'type': str, 'max': 255},
        'facebook': {'required': False, 'type': str, 'max': 255},
        'google': {'required': False, 'type': str, 'max': 255},
        'reviews': {'required': False, 'type': str, 'max': 500},
        'digital_marketing_requirement': {'required': False, 'type': str, 'max': 500},
        'software_requirment': {'required': False, 'type': str, 'max': 500},
        'mobileapp_requirement': {'required': False, 'type': str, 'max': 500},
        'website_requirement': {'required': False, 'type': str, 'max': 500},
        'remarks': {'required': False, 'type': str, 'max': 1000},
        'lead_indication': {'required': False, 'type': str, 'max': 50},
        'priority_score': {'required': False, 'type': int, 'min': 1, 'max': 10, 'default': 5}
    }
    
    for field, ruleset in rules.items():
        # Get value
        value = data.get(field, '').strip() if isinstance(data.get(field), str) else data.get(field, '')
        
        # Check required
        if ruleset.get('required', False) and not value:
            errors.append(f"{field.replace('_', ' ').title()} is required")
            continue
            
        # Skip empty optional fields
        if not value and not ruleset.get('required', False):
            validated[field] = '' if ruleset['type'] == str else None
            continue
        
        # Type conversion and validation
        try:
            if ruleset['type'] == int:
                val = int(value)
                if 'min' in ruleset and val < ruleset['min']:
                    errors.append(f"{field.replace('_', ' ').title()} must be at least {ruleset['min']}")
                if 'max' in ruleset and val > ruleset['max']:
                    errors.append(f"{field.replace('_', ' ').title()} must be at most {ruleset['max']}")
                validated[field] = val
            else:
                val = str(value)
                if 'max' in ruleset and len(val) > ruleset['max']:
                    errors.append(f"{field.replace('_', ' ').title()} must be less than {ruleset['max']} characters")
                if 'pattern' in ruleset and not re.match(ruleset['pattern'], val):
                    errors.append(ruleset['message'])
                validated[field] = val
                
        except ValueError:
            errors.append(f"{field.replace('_', ' ').title()} must be a valid number")
        except Exception as e:
            errors.append(f"Invalid value for {field.replace('_', ' ').title()}")
    
    # Auto-fix website URLs
    if validated.get('website') and validated['website']:
        website = validated['website']
        if not website.startswith(('http://', 'https://')):
            validated['website'] = 'https://' + website
    
    return errors, validated

def get_stats():
    """Get dashboard statistics"""
    try:
        with get_db_cursor() as cur:
            # Total leads
            cur.execute("SELECT COUNT(*) FROM business_db.business_leads")
            total = cur.fetchone()[0]
            
            # High priority (priority_score >= 8)
            cur.execute("SELECT COUNT(*) FROM business_db.business_leads WHERE priority_score >= 8")
            high = cur.fetchone()[0]
            
            # This month (using created_at column)
            cur.execute("""
                SELECT COUNT(*) FROM business_db.business_leads 
                WHERE EXTRACT(MONTH FROM created_at) = EXTRACT(MONTH FROM CURRENT_DATE)
                AND EXTRACT(YEAR FROM created_at) = EXTRACT(YEAR FROM CURRENT_DATE)
            """)
            this_month = cur.fetchone()[0]
            
            return {'total': total, 'high_priority': high, 'this_month': this_month}
    except Exception as e:
        app.logger.error(f"Error getting stats: {e}")
        return {'total': 0, 'high_priority': 0, 'this_month': 0}

@app.route("/")
@login_required
def home():
    stats = get_stats()
    return render_template("home.html", stats=stats)

@app.route("/new")
@login_required
def new_entry():
    return render_template("home.html", show_form=True)

@app.route("/insert", methods=["POST"])
@login_required
def insert():
    try:
        # Get form data
        form_data = {key: request.form.get(key, '') for key in request.form}
        
        # Validate form data
        errors, validated_data = validate_form_data(form_data)
        
        if errors:
            for error in errors:
                flash(error)
            return render_template("home.html", show_form=True, form_data=form_data)

        # Prepare data tuple for insertion
        data_tuple = (
            validated_data['business_name'],
            validated_data['city'],
            validated_data['category_type'],
            validated_data.get('address', ''),
            validated_data['contact_number'],
            validated_data.get('whatsapp', ''),
            validated_data.get('email', ''),
            validated_data.get('website', ''),
            validated_data.get('instagram', ''),
            validated_data.get('facebook', ''),
            validated_data.get('google', ''),
            validated_data.get('reviews', ''),
            validated_data.get('digital_marketing_requirement', ''),
            validated_data.get('software_requirment', ''),
            validated_data.get('mobileapp_requirement', ''),
            validated_data.get('website_requirement', ''),
            validated_data.get('remarks', ''),
            validated_data.get('lead_indication', ''),
            validated_data.get('priority_score', 5)
        )

        with get_db_cursor(commit=True) as cur:
            cur.execute("""
            INSERT INTO business_db.business_leads(
                business_name, city, category_type, address, contact_number,
                whatsapp, email, website, instagram, facebook, google, reviews,
                digital_marketing_requirement, software_requirment,
                mobileapp_requirement, website_requirement, remarks,
                lead_indication, priority_score
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, data_tuple)

        flash("✅ Entry added successfully!")
        app.logger.info(f"New entry inserted by {request.remote_addr}")

    except Exception as e:
        app.logger.error(f"Insert error: {e}")
        flash(f"❌ Error adding entry: {str(e)}")

    return redirect(url_for("home"))

@app.route("/show")
@login_required
def show():
    # Pagination parameters
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page

    # Get search filters from URL query parameters
    city_filter = request.args.get('city', '').strip()
    category_filter = request.args.get('category', '').strip()

    # Fetch distinct cities and categories for dropdowns (unchanged)
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT DISTINCT city FROM business_db.business_leads WHERE city IS NOT NULL AND city != '' ORDER BY city")
            cities = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT DISTINCT category_type FROM business_db.business_leads WHERE category_type IS NOT NULL AND category_type != '' ORDER BY category_type")
            categories = [row[0] for row in cur.fetchall()]
    except Exception as e:
        app.logger.error(f"Error fetching filter options: {e}")
        cities = []
        categories = []

    # Build conditions based on filters
    conditions = []
    params = []

    if city_filter:
        conditions.append("city = %s")
        params.append(city_filter)
    if category_filter:
        conditions.append("category_type = %s")
        params.append(category_filter)

    # First, get the total count (for pagination)
    count_query = "SELECT COUNT(*) FROM business_db.business_leads"
    if conditions:
        count_query += " WHERE " + " AND ".join(conditions)

    try:
        with get_db_cursor() as cur:
            cur.execute(count_query, params)
            total = cur.fetchone()[0]
    except Exception as e:
        app.logger.error(f"Count query error: {e}")
        total = 0

    # Now get the paginated data
    data_query = "SELECT * FROM business_db.business_leads"
    if conditions:
        data_query += " WHERE " + " AND ".join(conditions)
    data_query += " ORDER BY id DESC LIMIT %s OFFSET %s"

    # Add limit and offset to the parameters
    paginated_params = params + [per_page, offset]

    try:
        with get_db_cursor() as cur:
            cur.execute(data_query, paginated_params)
            rows = cur.fetchall()
    except Exception as e:
        app.logger.error(f"Data query error: {e}")
        rows = []
        flash(f"❌ Error loading data: {str(e)}")

    # Determine if there are more records
    has_more = (offset + per_page) < total

    return render_template("home.html",
                           rows=rows,
                           cities=cities,
                           categories=categories,
                           search_city=city_filter,
                           search_category=category_filter,
                           page=page,
                           has_more=has_more,
                           total=total)
        
@app.route("/edit/<id>")
@login_required
def edit(id):
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT * FROM business_db.business_leads WHERE id=%s", (id,))
            row = cur.fetchone()
        
        if not row:
            flash(f"❌ Record {id} not found")
            return redirect(url_for("show"))
            
        return render_template("home.html", edit=row, show_form=True)
    except Exception as e:
        app.logger.error(f"Edit error: {e}")
        flash(f"❌ Error: {str(e)}")
        return redirect(url_for("show"))

@app.route("/update/<id>", methods=["POST"])
@login_required
def update(id):
    try:
        # Get form data
        form_data = {key: request.form.get(key, '') for key in request.form}
        
        # Validate form data
        errors, validated_data = validate_form_data(form_data)
        
        if errors:
            for error in errors:
                flash(error)
            # Get the current record to show in form
            with get_db_cursor() as cur:
                cur.execute("SELECT * FROM business_db.business_leads WHERE id=%s", (id,))
                row = cur.fetchone()
            return render_template("home.html", edit=row, show_form=True, form_data=form_data)

        # Prepare data tuple for update
        data_tuple = (
            validated_data['business_name'],
            validated_data['city'],
            validated_data['category_type'],
            validated_data.get('address', ''),
            validated_data['contact_number'],
            validated_data.get('whatsapp', ''),
            validated_data.get('email', ''),
            validated_data.get('website', ''),
            validated_data.get('instagram', ''),
            validated_data.get('facebook', ''),
            validated_data.get('google', ''),
            validated_data.get('reviews', ''),
            validated_data.get('digital_marketing_requirement', ''),
            validated_data.get('software_requirment', ''),
            validated_data.get('mobileapp_requirement', ''),
            validated_data.get('website_requirement', ''),
            validated_data.get('remarks', ''),
            validated_data.get('lead_indication', ''),
            validated_data.get('priority_score', 5),
            id
        )

        with get_db_cursor(commit=True) as cur:
            cur.execute("""
            UPDATE business_db.business_leads SET
                business_name=%s,
                city=%s,
                category_type=%s,
                address=%s,
                contact_number=%s,
                whatsapp=%s,
                email=%s,
                website=%s,
                instagram=%s,
                facebook=%s,
                google=%s,
                reviews=%s,
                digital_marketing_requirement=%s,
                software_requirment=%s,
                mobileapp_requirement=%s,
                website_requirement=%s,
                remarks=%s,
                lead_indication=%s,
                priority_score=%s
            WHERE id=%s
            """, data_tuple)

        flash("✅ Data updated successfully!")
        app.logger.info(f"Record {id} updated by {request.remote_addr}")

    except Exception as e:
        app.logger.error(f"Update error: {e}")
        flash(f"❌ Error updating: {str(e)}")

    return redirect(url_for("show"))

@app.route("/delete/<id>", methods=["POST"])
@login_required
def delete(id):
    try:
        with get_db_cursor(commit=True) as cur:
            cur.execute("DELETE FROM business_db.business_leads WHERE id=%s", (id,))
        
        flash(f"✅ Record {id} deleted successfully")
        app.logger.info(f"Record {id} deleted by {request.remote_addr}")
        
    except Exception as e:
        app.logger.error(f"Delete error: {e}")
        flash(f"❌ Error deleting record: {str(e)}")
    
    return redirect(url_for("show"))

@app.route("/health")
@login_required
def health():
    """Health check endpoint"""
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}, 200
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}, 500

# Clean up on exit
@atexit.register
@login_required
def close_pool():
    if connection_pool:
        connection_pool.closeall()
        app.logger.info("Connection pool closed")

if __name__ == "__main__":
    # For production, use gunicorn instead
    app.run(host="0.0.0.0", port=5000, debug=False)