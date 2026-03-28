from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from db import get_db_cursor
from datetime import datetime, timedelta

leave_bp = Blueprint('leave', __name__, url_prefix='/leave')

@leave_bp.route('/', methods=['GET', 'POST'])
@login_required
def apply():
    if request.method == 'POST':
        leave_type = request.form.get('leave_type')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        reason = request.form.get('reason', '')

        if not leave_type or not start_date or not end_date:
            flash('All fields are required.')
            return redirect(url_for('leave.apply'))

        if start_date > end_date:
            flash('End date cannot be before start date.')
            return redirect(url_for('leave.apply'))

        try:
            with get_db_cursor(commit=True) as cur:
                cur.execute("""
                    INSERT INTO business_db.leave_applications
                    (user_id, username, leave_type, start_date, end_date, reason)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (current_user.id, current_user.username, leave_type, start_date, end_date, reason))
            flash('✅ Leave application submitted successfully!')
        except Exception as e:
            flash(f'❌ Error: {str(e)}')
        return redirect(url_for('leave.apply'))

    return render_template('leave_apply.html')


@leave_bp.route('/history')
@login_required
def history():
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT id, leave_type, start_date, end_date, reason, status, created_at
            FROM business_db.leave_applications
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (current_user.id,))
        rows = cur.fetchall()

    now = datetime.utcnow()
    leaves = []
    for row in rows:
        created_at = row[6]
        is_editable = (now - created_at) <= timedelta(hours=6)
        leaves.append(row + (is_editable,))   # append flag to the tuple

    return render_template('leave_history.html', leaves=leaves)


@leave_bp.route('/edit/<int:leave_id>', methods=['GET', 'POST'])
@login_required
def edit(leave_id):
    # Fetch the leave record
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT id, leave_type, start_date, end_date, reason, user_id, created_at
            FROM business_db.leave_applications
            WHERE id = %s
        """, (leave_id,))
        leave = cur.fetchone()

    if not leave:
        flash("Leave application not found.")
        return redirect(url_for('leave.history'))

    # Check ownership
    if leave[5] != current_user.id:
        flash("You are not authorized to edit this leave.")
        return redirect(url_for('leave.history'))

    # Check 6-hour window
    now = datetime.utcnow()
    created_at = leave[6]
    if (now - created_at) > timedelta(hours=6):
        flash("You can only edit leave applications within 6 hours of submission.")
        return redirect(url_for('leave.history'))

    if request.method == 'POST':
        leave_type = request.form.get('leave_type')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        reason = request.form.get('reason', '')

        if not leave_type or not start_date or not end_date:
            flash("All fields are required.")
            return redirect(url_for('leave.edit', leave_id=leave_id))

        if start_date > end_date:
            flash("End date cannot be before start date.")
            return redirect(url_for('leave.edit', leave_id=leave_id))

        try:
            with get_db_cursor(commit=True) as cur:
                cur.execute("""
                    UPDATE business_db.leave_applications
                    SET leave_type = %s,
                        start_date = %s,
                        end_date = %s,
                        reason = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND user_id = %s
                """, (leave_type, start_date, end_date, reason, leave_id, current_user.id))
            flash("✅ Leave application updated successfully.")
            return redirect(url_for('leave.history'))
        except Exception as e:
            flash(f"❌ Error updating: {str(e)}")
            return redirect(url_for('leave.edit', leave_id=leave_id))

    return render_template('leave_apply.html', edit_mode=True, leave=leave)


@leave_bp.route('/delete/<int:leave_id>', methods=['POST'])
@login_required
def delete(leave_id):
    # Fetch leave to check ownership and time
    with get_db_cursor() as cur:
        cur.execute("SELECT user_id, created_at FROM business_db.leave_applications WHERE id = %s", (leave_id,))
        row = cur.fetchone()
        if not row:
            flash("Leave not found.")
            return redirect(url_for('leave.history'))
        if row[0] != current_user.id:
            flash("You are not authorized to delete this leave.")
            return redirect(url_for('leave.history'))
        # Check 6-hour window
        now = datetime.utcnow()
        created_at = row[1]
        if (now - created_at) > timedelta(hours=6):
            flash("You can only delete leave applications within 6 hours of submission.")
            return redirect(url_for('leave.history'))

    # Delete
    try:
        with get_db_cursor(commit=True) as cur:
            cur.execute("DELETE FROM business_db.leave_applications WHERE id = %s AND user_id = %s",
                        (leave_id, current_user.id))
        flash("✅ Leave application deleted successfully.")
    except Exception as e:
        flash(f"❌ Error deleting: {str(e)}")
    return redirect(url_for('leave.history'))

# Admin panel – only for user with id 3 (Jinesh)
@leave_bp.route('/admin')
@login_required
def admin():
    if current_user.id != 3:   # Restrict to user ID 3
        flash("Access denied.")
        return redirect(url_for('leave.history'))

    with get_db_cursor() as cur:
        cur.execute("""
            SELECT l.id, l.username, l.leave_type, l.start_date, l.end_date,
                   l.reason, l.status, l.created_at, u.email
            FROM business_db.leave_applications l
            LEFT JOIN business_db.users u ON l.user_id = u.id
            ORDER BY l.created_at DESC
        """)
        leaves = cur.fetchall()
    return render_template('leave_admin.html', leaves=leaves)

@leave_bp.route('/admin/update/<int:leave_id>', methods=['POST'])
@login_required
def admin_update(leave_id):
    if current_user.id != 3:
        flash("Access denied.")
        return redirect(url_for('leave.history'))

    new_status = request.form.get('status')
    if new_status not in ['Approved', 'Denied']:
        flash("Invalid status.")
        return redirect(url_for('leave.admin'))

    try:
        with get_db_cursor(commit=True) as cur:
            cur.execute("""
                UPDATE business_db.leave_applications
                SET status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (new_status, leave_id))
        flash(f"Leave #{leave_id} updated to {new_status}.")
    except Exception as e:
        flash(f"Error updating: {e}")

    return redirect(url_for('leave.admin'))