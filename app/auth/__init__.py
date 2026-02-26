"""
app/auth.py — Authentication Blueprint.

Routes: /login, /logout, /change-password
"""

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, session,
)

import auth_db as _auth_db
from app.utils import login_required

bp = Blueprint('auth', __name__, template_folder='templates')

MIN_PASSWORD_LENGTH = 6  # Minimum acceptable password length


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Display and process the login form."""
    if 'username' in session:
        return redirect(url_for('common.index'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = _auth_db.get_user(username)
        if user and _auth_db.verify_password(password, user['password_hash']):
            session['username'] = username
            session['must_change_password'] = bool(user['must_change_password'])
            if user['must_change_password']:
                flash('Please set a new password before continuing.', 'warning')
                return redirect(url_for('auth.change_password'))
            return redirect(url_for('common.index'))
        error = 'Invalid username or password.'

    return render_template('auth/login.html', error=error)


@bp.route('/logout')
def logout():
    """Clear session and redirect to the login page."""
    session.clear()
    return redirect(url_for('auth.login'))


@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Allow the current user to change their password."""
    error = None
    if request.method == 'POST':
        current = request.form.get('current_password', '')
        new_pw  = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')

        user = _auth_db.get_user(session['username'])
        if not user or not _auth_db.verify_password(current, user['password_hash']):
            error = 'Current password is incorrect.'
        elif len(new_pw) < MIN_PASSWORD_LENGTH:
            error = f'New password must be at least {MIN_PASSWORD_LENGTH} characters.'
        elif new_pw != confirm:
            error = 'Passwords do not match.'
        else:
            _auth_db.update_password(session['username'], new_pw)
            session['must_change_password'] = False
            flash('Password changed successfully.', 'success')
            return redirect(url_for('common.index'))

    return render_template('auth/change_password.html', error=error)
