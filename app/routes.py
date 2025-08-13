from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, abort, send_file, \
    make_response
from flask_login import login_user, login_required, logout_user, current_user
from datetime import date, datetime, timedelta
from sqlalchemy.exc import SQLAlchemyError
from .models import *
from .forms import *
from wtforms import FieldList, FormField
from . import oauth
import os
import io
from pprint import pprint
import pandas as pd
from fpdf import FPDF

bp = Blueprint('main', __name__)

ADMIN_EMAILS = os.getenv('ADMIN_EMAILS', '')

weeks = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
         21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38]



# ######### ERROR HANDLERS ########

from flask import render_template

@bp.errorhandler(404)
def not_found_error(error):
    return render_template(
        "error.html",
        title="Page Not Found",
        heading="Page Not Found",
        message="The page you requested could not be found.",
        code=404
    ), 404


@bp.errorhandler(500)
def internal_error(error):
    return render_template(
        "error.html",
        title="Server Error",
        heading="Internal Server Error",
        message="Something went wrong on our end. Please try again later.",
        code=500
    ), 500


@bp.route("/test-error")
def test_error():
    return render_template(
        "error.html",
        title="Custom Error",
        heading="Access Denied",
        message="You do not have permission to view this page.",
        code=403
    ), 403



@bp.route('/')
def index():
    try:
        now = datetime.utcnow()
        active_match_weeks = MatchWeek.query.filter(MatchWeek.predictions_close_time > now).all()
        return render_template('index.html', active_match_weeks=active_match_weeks)
    except SQLAlchemyError as e:
        flash(f'Database error: {str(e)}', 'error')
        return render_template('error.html', error_message='Could not retrieve active match weeks.')


@bp.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    return render_template('login.html')


@bp.route('/authorize/google')
def google_auth():
    redirect_uri = url_for('main.google_callback', _external=True)
    try:
        return oauth.google.authorize_redirect(redirect_uri)
    except Exception as e:
        flash(f'Google authorization failed: {str(e)}', 'error')
        return redirect(url_for('main.login'))


@bp.route('/authorize/google/callback')
def google_callback():
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo')
    except Exception as e:
        flash(f'Authentication failed: {str(e)}', 'error')
        return redirect(url_for('main.login'))

    if not user_info:
        flash('Authentication failed', 'error')
        return redirect(url_for('main.login'))

    user = User.query.filter_by(google_id=user_info.get('sub')).first()

    if not user:
        user = User.query.filter_by(email=user_info.get('email')).first()

    if not user:
        is_admin = 1 if user_info.get('email') in ADMIN_EMAILS.split(',') else 0
        return redirect(url_for(
            'main.set_nickname',
            google_id=user_info.get('sub'),
            email=user_info.get('email'),
            name=user_info.get('name'),
            is_admin=is_admin
        ))
    try:
        user.google_id = user_info.get('sub')
        user.name = user_info.get('name')
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Database error during user update: {str(e)}', 'error')
        return redirect(url_for('main.login'))

    login_user(user)
    flash('Successfully logged in!', 'success')
    return redirect(url_for('main.index'))


@bp.route('/user/set-nickname', methods=['GET', 'POST'])
def set_nickname():
    google_id = request.args.get('google_id')
    email = request.args.get('email')
    name = request.args.get('name')
    is_admin = int(request.args.get('is_admin', 0))

    if not all([google_id, email, name]):
        flash('Missing required user information. Please try logging in again.', 'error')
        return redirect(url_for('main.login'))

    form = NameForm()

    if request.method == 'GET':
        form.name.data = name
        form.email.data = email
        form.google_id.data = google_id

    if form.validate_on_submit():
        try:
            user = User(
                nickname=form.nickname.data,
                email=form.email.data,
                name=form.name.data,
                google_id=google_id,
                is_admin=bool(is_admin)
            )
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Account created and logged in!', 'success')
            return redirect(url_for('main.index'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Error creating user: {str(e)}', 'error')
            return redirect(url_for('main.login'))

    return render_template('admin/form.html', title='Set Nickname', heading='Set Nickname', form=form)


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('main.index'))


@bp.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.index'))
    try:
        now = datetime.utcnow()
        users = User.query.order_by(User.id).all()
        match_weeks = MatchWeek.query.order_by(MatchWeek.id).all()
        seasons = Season.query.order_by(Season.id).all()
        teams = Team.query.order_by(Team.id).all()
        return render_template('admin/dashboard.html', title='Admin Panel', now=now,
                               users=users, match_weeks=match_weeks, seasons=seasons, teams=teams)
    except SQLAlchemyError as e:
        flash(f'Database error: {str(e)}', 'error')
        return redirect(url_for('main.index'))


@bp.route('/create_weeks', methods=['GET', 'POST'])
@login_required
def create_weeks():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.index'))
    try:
        weeks_to_create = []
        for week_num in range(1, 39):
            if not Week.query.filter_by(week_number=week_num).first():
                weeks_to_create.append(Week(week_number=week_num))

        if weeks_to_create:
            db.session.add_all(weeks_to_create)
            db.session.commit()
            flash('Weeks created successfully!', 'success')
        else:
            flash('All weeks already exist. No new weeks were created.', 'info')

        return redirect(url_for('main.admin_dashboard'))
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Error creating weeks: {str(e)}', 'error')
        return redirect(url_for('main.admin_dashboard'))


@bp.route('/admin/teams/populate', methods=['GET', 'POST'])
@login_required
def populate_teams():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.index'))

    populated_count = 0
    try:
        for team_dict in EPL_TEAMS:
            for short_name, name in team_dict.items():
                if not Team.query.filter_by(name=name.strip()).first():
                    new_team = Team(name=name.strip(), short_name=short_name.strip())
                    db.session.add(new_team)
                    populated_count += 1

        db.session.commit()
        if populated_count > 0:
            flash(f'{populated_count} teams populated successfully!', 'success')
        else:
            flash('All teams already exist. No new teams were added.', 'info')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Error populating teams: {str(e)}', 'error')

    return redirect(request.referrer)


@bp.route('/admin/team/edit/<int:team_id>', methods=['GET', 'POST'])
@login_required
def edit_team(team_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.index'))

    try:
        team = Team.query.get_or_404(team_id)
    except SQLAlchemyError:
        abort(500)

    form = CreateTeamForm(obj=team)
    if form.validate_on_submit():
        try:
            form.populate_obj(team)
            team.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Team Updated.', 'success')
            return redirect(url_for('main.admin_dashboard'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Error updating team: {str(e)}', 'error')

    return render_template('admin/select_form.html', heading='Create/Edit Team', title='Create team', form=form)


@bp.route('/admin/test_route')
@login_required
def test_route():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.index'))

    print("=== TEST ROUTE CALLED ===")
    return "Test route works!"


@bp.route('/admin/create_match_week', methods=['GET', 'POST'])
@login_required
def create_match_week():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.index'))

    try:
        weeks_db = Week.query.order_by(Week.id).all()
        seasons_db = Season.query.order_by(Season.season_start_year.asc()).all()
        teams_db = Team.query.order_by(Team.name).all()

        if not weeks_db or not seasons_db or not teams_db:
            flash('Required database tables (Weeks, Seasons, or Teams) are empty. Please populate them first.', 'error')
            return redirect(url_for('main.admin_dashboard'))

        week_choices = [(str(w.id), f"Week {w.week_number}") for w in weeks_db]
        season_choices = [(str(s.id), f"{s.season_start_year}-{s.season_end_year}") for s in seasons_db]
        team_choices = [(str(t.id), t.name) for t in teams_db]

        class DynamicCreateMatchWeekForm(CreateMatchWeekForm):
            fixtures = FieldList(FormField(FixtureForm), min_entries=1, max_entries=20)

        form = DynamicCreateMatchWeekForm()
        form.week_number.choices = week_choices
        form.season.choices = season_choices
        for fixture_form in form.fixtures:
            fixture_form.home_team.choices = team_choices
            fixture_form.away_team.choices = team_choices

    except SQLAlchemyError as e:
        flash(f'Database error: {str(e)}', 'error')
        return redirect(url_for('main.admin_dashboard'))

    if form.validate_on_submit():
        try:
            match_week = MatchWeek(
                week_id=form.week_number.data,
                season_id=form.season.data,
                predictions_open_time=form.predictions_open_time.data,
                predictions_close_time=form.predictions_close_time.data
            )

            db.session.add(match_week)
            db.session.flush()

            fixture_count = 0
            for fixture_form in form.fixtures:
                if fixture_form.home_team.data and fixture_form.away_team.data:
                    fixture = Fixture(
                        match_week_id=match_week.id,
                        home_team_id=fixture_form.home_team.data,
                        away_team_id=fixture_form.away_team.data,
                    )
                    db.session.add(fixture)
                    fixture_count += 1

            db.session.commit()
            flash(f'Match Week created successfully with {fixture_count} fixtures!', 'success')
            return redirect(url_for('main.admin_dashboard'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Error creating match week: {str(e)}', 'error')
            return redirect(url_for('main.admin_dashboard'))

    elif request.method == 'POST':
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Error in field {field}: {error}', 'error')

    return render_template('admin/create_match_week.html', form=form)


@bp.route('/admin/edit_match_week/<int:match_week_id>', methods=['GET', 'POST'])
@login_required
def edit_match_week(match_week_id):
    if not current_user.is_admin:
        flash('Access denied!', 'danger')
        return redirect(url_for('main.index'))
    try:
        match_week = MatchWeek.query.get_or_404(match_week_id)
        weeks = Week.query.order_by(Week.id).all()
        season = Season.query.filter_by(id=match_week.season_id).first_or_404()
    except SQLAlchemyError:
        abort(500)

    form = MatchWeekUpdateForm()
    form.season.choices = [(str(season.id), f"{season.season_start_year}/{season.season_end_year}")]
    form.week_number.choices = [(str(week.id), f"Week {week.week_number}") for week in weeks]

    if request.method == 'GET':
        form.predictions_open_time.data = match_week.predictions_open_time
        form.predictions_close_time.data = match_week.predictions_close_time
        form.season.data = str(match_week.season_id)
        form.week_number.data = str(match_week.week_id)

    if form.validate_on_submit():
        try:
            match_week.season_id = int(form.season.data)
            match_week.week_id = int(form.week_number.data)
            match_week.predictions_open_time = form.predictions_open_time.data
            match_week.predictions_close_time = form.predictions_close_time.data
            db.session.commit()
            flash('Match week updated.', 'success')
            return redirect(url_for('main.admin_dashboard'))
        except (ValueError, SQLAlchemyError) as e:
            db.session.rollback()
            flash(f'Error updating match week: {str(e)}', 'error')
            return redirect(url_for('main.admin_dashboard'))

    return render_template('admin/select_form.html', heading='Edit Match Week', title='Edit Match Week', form=form)


@bp.route('/admin/create_season', methods=['GET', 'POST'])
@login_required
def create_season():
    if not current_user.is_admin:
        flash('Access denied!', 'danger')
        return redirect(url_for('main.index'))

    form = CreateSeasonForm()
    if form.validate_on_submit():
        start = form.start_year.data
        end = form.end_year.data
        try:
            if Season.query.filter_by(season_start_year=start, season_end_year=end).first():
                flash('Season exists', 'warning')
            else:
                db.session.add(
                    Season(
                        season_start_year=start,
                        season_end_year=end
                    )
                )
                db.session.commit()
                flash('Season created successfully.', 'success')
                return redirect(url_for('main.admin_dashboard'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Error creating season: {str(e)}', 'danger')
    return render_template('admin/create_season.html', form=form)


@bp.route('/print-fixtures/<int:match_week_id>')
def print_fixtures(match_week_id):
    try:
        match_week = MatchWeek.query.get_or_404(match_week_id)
        return render_template('print_fixtures.html', week=match_week)
    except SQLAlchemyError:
        abort(500)


@bp.route('/admin/activate_match_week/<int:week_id>', methods=['POST'])
@login_required
def activate_match_week(week_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.index'))

    try:
        MatchWeek.query.filter_by(is_active=True).update({MatchWeek.is_active: False})
        match_week = MatchWeek.query.get_or_404(week_id)
        match_week.is_active = True
        db.session.commit()
        flash(f'Match Week {match_week.week.week_number} activated!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Error activating match week: {str(e)}', 'error')

    return redirect(url_for('main.admin_dashboard'))


@bp.route('/matches', methods=['GET', 'POST'])
@login_required
def predict():
    try:
        open_fixtures = Fixture.get_open_for_predictions()
    except SQLAlchemyError as e:
        flash(f'Database error: {str(e)}', 'error')
        return redirect(url_for('main.index'))

    if not open_fixtures:
        flash("Predictions not open at the moment", 'info')
        return redirect(url_for('main.index'))

    match_week_id = open_fixtures[0].match_week_id
    try:
        match_week = MatchWeek.query.get_or_404(match_week_id)
    except SQLAlchemyError:
        flash('Could not find the corresponding match week.', 'error')
        return redirect(url_for('main.index'))

    user_predictions = {}
    if current_user.is_authenticated:
        fixture_ids = [fixture.id for fixture in open_fixtures]
        try:
            existing_predictions = Prediction.query.filter(
                Prediction.user_id == current_user.id,
                Prediction.fixture_id.in_(fixture_ids)
            ).all()
            for prediction in existing_predictions:
                user_predictions[prediction.fixture_id] = prediction
        except SQLAlchemyError as e:
            flash(f'Error retrieving existing predictions: {str(e)}', 'error')
            return redirect(url_for('main.index'))

    class DynamicMatchesForm():
        matches = FieldList(FormField(PredictionForm), min_entries=1, max_entries=20)
        submit = SubmitField('Submit Predictions')

    form = DynamicMatchesForm()

    while len(form.matches) < len(open_fixtures):
        form.matches.append_entry()
    while len(form.matches) > len(open_fixtures):
        form.matches.pop_entry()

    if request.method == 'GET':
        for i, fixture in enumerate(open_fixtures):
            if i < len(form.matches):
                form.matches[i].home_team.data = fixture.home_team.name
                form.matches[i].away_team.data = fixture.away_team.name

                if current_user.is_authenticated and fixture.id in user_predictions:
                    prediction = user_predictions[fixture.id]
                    form.matches[i].home_score.data = prediction.home_score_prediction
                    form.matches[i].away_score.data = prediction.away_score_prediction
                else:
                    form.matches[i].home_score.data = 0
                    form.matches[i].away_score.data = 0

    if form.validate_on_submit():
        user_id = current_user.id
        try:
            predictions_saved = 0
            for i, match_form in enumerate(form.matches):
                fixture = open_fixtures[i]
                existing_prediction = Prediction.query.filter_by(
                    user_id=user_id, fixture_id=fixture.id
                ).first()

                home_team = Team.query.filter_by(name=match_form.home_team.data).first()
                away_team = Team.query.filter_by(name=match_form.away_team.data).first()
                if not home_team or not away_team:
                    flash(f'Error: Could not find team data for match {i + 1}.', 'error')
                    continue

                if existing_prediction:
                    existing_prediction.home_team_id = home_team.id
                    existing_prediction.away_team_id = away_team.id
                    existing_prediction.home_score_prediction = match_form.home_score.data
                    existing_prediction.away_score_prediction = match_form.away_score.data
                    existing_prediction.updated_at = datetime.utcnow()
                else:
                    prediction = Prediction(
                        user_id=user_id,
                        fixture_id=fixture.id,
                        home_team_id=home_team.id,
                        away_team_id=away_team.id,
                        home_score_prediction=match_form.home_score.data,
                        away_score_prediction=match_form.away_score.data
                    )
                    db.session.add(prediction)
                predictions_saved += 1

            db.session.commit()
            flash(f'{predictions_saved} predictions saved successfully!', 'success')
            return redirect(url_for('main.index'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Error saving predictions: {str(e)}', 'error')
            return redirect(url_for('main.index'))
    elif request.method == 'POST':
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Error in field {field}: {error}', 'error')

    return render_template('predict.html', form=form, match_week=match_week, user_predictions=user_predictions,
                           fixtures=open_fixtures)