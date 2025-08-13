from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import func
from . import db

# Association tables (many-to-many)
season_week = db.Table(
    'season_week',
    db.Column('season_id', db.Integer, db.ForeignKey('season.id', ondelete="CASCADE"), primary_key=True),
    db.Column('week_id', db.Integer, db.ForeignKey('week.id', ondelete="CASCADE"), primary_key=True)
)

season_team = db.Table(
    'season_team',
    db.Column('season_id', db.Integer, db.ForeignKey('season.id', ondelete="CASCADE"), primary_key=True),
    db.Column('team_id', db.Integer, db.ForeignKey('team.id', ondelete="CASCADE"), primary_key=True)
)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    nickname = db.Column(db.String(100), nullable=False)
    google_id = db.Column(db.String(100), unique=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_points = db.Column(db.Integer, nullable=False, default=0)

    predictions = db.relationship('Prediction', backref='user', lazy=True, cascade="all, delete-orphan", passive_deletes=True)
    match_week_scores = db.relationship('MatchWeekPoint', backref='user', lazy=True, cascade="all, delete-orphan", passive_deletes=True)

    def __repr__(self):
        return f'<User {self.email}>'


class Season(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    season_start_year = db.Column(db.Integer, nullable=False)
    season_end_year = db.Column(db.Integer, nullable=False)

    match_weeks = db.relationship('MatchWeek', backref='season', lazy=True, cascade="all, delete-orphan", passive_deletes=True)

    def __repr__(self):
        return f'<Season {self.season_start_year}/{self.season_end_year}>'


class Week(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_number = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f'<Week {self.week_number}>'


class MatchWeek(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('season.id', ondelete="CASCADE"), nullable=False)
    week_id = db.Column(db.Integer, db.ForeignKey('week.id', ondelete="CASCADE"), nullable=False)

    week = db.relationship('Week', passive_deletes=True)
    predictions_open_time = db.Column(db.DateTime, nullable=False)
    predictions_close_time = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    fixtures = db.relationship('Fixture', backref='match_week', lazy=True, cascade="all, delete-orphan", passive_deletes=True)
    scores = db.relationship('MatchWeekPoint', backref='match_week', lazy=True, cascade="all, delete-orphan", passive_deletes=True)

    def __repr__(self):
        return f'<MatchWeek {self.week_id}: Season {self.season_id}>'

    @property
    def is_predictions_open(self):
        now = datetime.utcnow()
        return self.predictions_open_time <= now <= self.predictions_close_time


class Fixture(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_week_id = db.Column(db.Integer, db.ForeignKey('match_week.id', ondelete="CASCADE"), nullable=False)
    home_team_id = db.Column(db.Integer, db.ForeignKey('team.id', ondelete="SET NULL"), nullable=True)
    away_team_id = db.Column(db.Integer, db.ForeignKey('team.id', ondelete="SET NULL"), nullable=True)

    match_datetime = db.Column(db.DateTime, nullable=True)
    home_score = db.Column(db.Integer, nullable=True)
    away_score = db.Column(db.Integer, nullable=True)
    is_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    predictions = db.relationship('Prediction', backref='fixture', lazy=True, cascade="all, delete-orphan", passive_deletes=True)

    home_team = db.relationship('Team', foreign_keys=[home_team_id], backref='home_fixtures', passive_deletes=True)
    away_team = db.relationship('Team', foreign_keys=[away_team_id], backref='away_fixtures', passive_deletes=True)

    def __repr__(self):
        return f'<Fixture {self.home_team.name if self.home_team else "Unknown"} vs {self.away_team.name if self.away_team else "Unknown"}>'

    @classmethod
    def get_open_for_predictions(cls):
        now = datetime.utcnow()
        return cls.query.join(MatchWeek).filter(
            MatchWeek.predictions_open_time <= now,
            MatchWeek.predictions_close_time >= now
        ).all()


class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete="CASCADE"), nullable=False)
    fixture_id = db.Column(db.Integer, db.ForeignKey('fixture.id', ondelete="CASCADE"), nullable=False)
    home_team_id = db.Column(db.Integer, db.ForeignKey('team.id', ondelete="SET NULL"), nullable=True)
    away_team_id = db.Column(db.Integer, db.ForeignKey('team.id', ondelete="SET NULL"), nullable=True)

    home_score_prediction = db.Column(db.Integer, nullable=False)
    away_score_prediction = db.Column(db.Integer, nullable=False)
    points_earned = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    home_team = db.relationship('Team', foreign_keys=[home_team_id], backref='home_predictions', passive_deletes=True)
    away_team = db.relationship('Team', foreign_keys=[away_team_id], backref='away_predictions', passive_deletes=True)


class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    short_name = db.Column(db.String(10), nullable=True)
    logo_url = db.Column(db.String(200), nullable=True)
    nickname = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Team {self.name}>'


class MatchWeekPoint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete="CASCADE"), nullable=False)
    match_week_id = db.Column(db.Integer, db.ForeignKey('match_week.id', ondelete="CASCADE"), nullable=False)

    rank = db.Column(db.Integer, nullable=True)
    points = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def rank_user(self):
        scores = MatchWeekPoint.query.filter_by(match_week_id=self.match_week_id) \
            .order_by(MatchWeekPoint.points.desc()).all()
        rank = 1
        for score in scores:
            if score.user_id == self.user_id:
                self.rank = rank
                break
            rank += 1

    def __repr__(self):
        return f'<MatchWeekPoint User {self.user_id} Week {self.match_week_id} Points {self.points}>'
