"""
Hackathon API endpoints - create/update/delete/list hackathons+leaderboards
"""

import datetime
import uuid

import arrow
import flask
import sqlalchemy

from .. import model, util
from .. import response_success
from ..util import cross_origin

from .util import get_offset_limit, get_sort_filter, hackathon_status, \
    is_user_admin, requires_admin, requires_oauth_login
from .blueprint import web_api


def can_view_hackathon(user_id, hackathon_id, conn):
    is_user_joined = conn.execute(model.hackathon_participants.select(
        (model.hackathon_participants.c.user_id == user_id) &
        (model.hackathon_participants.c.hackathon_id == hackathon_id)
    )).first()

    is_admin = is_user_admin(user_id, conn=conn)

    return is_user_joined or is_admin


hackathon_query = sqlalchemy.sql.select([
    model.hackathons.c.id,
    model.hackathons.c.title,
    model.hackathons.c.description,
    model.hackathons.c.start_date,
    model.hackathons.c.end_date,
    model.hackathons.c.organization_id,
    model.organizations.c.organization_name,
]).select_from(
    model.hackathons.join(
        model.organizations,
        model.hackathons.c.organization_id == model.organizations.c.id,
        isouter=True,
        )
)


@web_api.route("/hackathon", methods=["GET"])
@requires_admin(accept_key=True)
def list_hackathons(*, admin_id):
    result = []
    offset, limit = get_offset_limit()

    with model.engine.connect() as conn:
        hackathons = conn.execute(
            hackathon_query.offset(offset).limit(limit)).fetchall()

        for hackathon in hackathons:
            record = {
                "hackathon_id": hackathon["id"],
                "title": hackathon["title"],
                "description": hackathon["description"],
                "status": hackathon_status(hackathon["start_date"],
                                           hackathon["end_date"]),
                "start_date": hackathon["start_date"],
                "end_date": hackathon["end_date"],
                "organization_id": hackathon["organization_id"],
                "organization_name": hackathon["organization_name"],
            }

            result.append(record)

    return flask.jsonify(result)


@web_api.route("/hackathon", methods=["POST"])
@requires_admin(accept_key=True)
def create_hackathon(*, admin_id):
    title = flask.request.form["title"]
    description = flask.request.form["description"]
    start_date = arrow.get(flask.request.form["start_date"]).datetime
    organization_id = flask.request.form.get("organization_id")

    with model.engine.connect() as conn:
        if organization_id is not None:
            organization_id = int(organization_id)
            organization = conn.execute(
                model.organizations.select(model.organizations.c.id == organization_id)
            ).first()

            if not organization:
                raise util.APIError(
                    400,
                    message="Invalid organization ID."
                )

        verification_code = uuid.uuid4().hex
        hackathon_id = conn.execute(model.hackathons.insert().values(
            title=title,
            description=description,
            start_date=start_date,
            end_date=None,
            verification_code=verification_code,
            organization_id=organization_id,
        )).inserted_primary_key[0]

        return response_success({
            "hackathon_id": hackathon_id,
            "verification_code": verification_code,
        })


@web_api.route("/hackathon/<int:hackathon_id>", methods=["GET"])
@cross_origin(methods=["GET", "PUT"])
@requires_oauth_login
def get_hackathon(hackathon_id, *, user_id):
    with model.engine.connect() as conn:
        hackathon = conn.execute(hackathon_query.where(
            model.hackathons.c.id == hackathon_id)).first()

        if not hackathon or not can_view_hackathon(user_id, hackathon["id"], conn):
            raise util.APIError(404)

        # TODO: num of participants

        return flask.jsonify({
            "hackathon_id": hackathon["id"],
            "title": hackathon["title"],
            "description": hackathon["description"],
            "status": hackathon_status(hackathon["start_date"],
                                       hackathon["end_date"]),
            "start_date": hackathon["start_date"],
            "end_date": hackathon["end_date"],
            "organization_id": hackathon["organization_id"],
            "organization_name": hackathon["organization_name"],
        })


@web_api.route("/hackathon/<int:hackathon_id>", methods=["PUT"])
@cross_origin(methods=["GET", "PUT"])
@requires_admin(accept_key=True)
def update_hackathon(hackathon_id, *, admin_id):
    values = {}

    if "title" in flask.request.form:
        values["title"] = flask.request.form["title"]

    if "description" in flask.request.form:
        values["description"] = flask.request.form["description"]

    if "start_date" in flask.request.form:
        values["start_date"] = \
            arrow.get(flask.request.form["start_date"]).datetime

    if "end_date" in flask.request.form:
        values["end_date"] = \
            arrow.get(flask.request.form["end_date"]).datetime

    if "organization_id" in flask.request.form:
        values["organization_id"] = int(flask.request.form["organization_id"])

    close_hackathon = False
    if "close" in flask.request.form:
        close_hackathon = flask.request.form["close"] == "true"

    with model.engine.connect() as conn:
        hackathon = conn.execute(
            model.hackathons.select(model.hackathons.c.id == hackathon_id)
        ).first()

        if not hackathon:
            raise util.APIError(
                404,
                message="Hackathon does not exist."
            )

        if "organization_id" in values:
            organization_id = int(values["organization_id"])
            organization = conn.execute(
                model.organizations.select(model.organizations.c.id == organization_id)
            ).first()

            if not organization:
                raise util.APIError(
                    400,
                    message="Invalid organization ID."
                )

        start_date = values.get("start_date", hackathon["start_date"])
        end_date = values.get("end_date", hackathon["end_date"])
        if end_date and start_date >= end_date:
            raise util.APIError(
                400,
                message="Start date must be before end date."
            )

        # Close the competition
        if close_hackathon:
            if end_date and end_date > datetime.datetime.now():
                raise util.APIError(
                    400,
                    message="Cannot end a competition with an end date in "
                            "the future. If the hackathon had an end date "
                            "specified, then either specify a new end date "
                            "or wait for the end date to pass. Otherwise, "
                            "specify an end date in the past. "
                )
            elif not end_date:
                values["end_date"] = arrow.now()

            # Snapshot all the ranks
            # TODO:

        conn.execute(model.hackathons.update().values(**values).where(
            model.hackathons.c.id == hackathon_id
        ))

        return response_success({
            "hackathon_id": hackathon_id,
            "updated_values": values,
        })


@web_api.route("/hackathon/<int:hackathon_id>/leaderboard", methods=["GET"])
@cross_origin(methods=["GET"])
@requires_oauth_login
def get_hackathon_leaderboard(hackathon_id, *, user_id):
    with model.engine.connect() as conn:
        if not can_view_hackathon(user_id, hackathon_id, conn):
            raise util.APIError(404)

        table = model.hackathon_ranked_bots_users_query(hackathon_id)

        result = []
        offset, limit = get_offset_limit()

        where_clause, order_clause, _ = get_sort_filter({
            "user_id": table.c.user_id,
            "username": table.c.username,
            "level": table.c.player_level,
            "organization_id": table.c.organization_id,
            "version_number": table.c.num_submissions,
            "num_games": table.c.num_games,
            "global_rank": table.c.global_rank,
            "local_rank": table.c.local_rank,
            "language": table.c.language,
        })

        if not order_clause:
            order_clause = [table.c.local_rank]

        total_users = conn.execute(model.total_ranked_users).first()[0]
        hackathon_users = conn.execute(
            model.hackathon_total_ranked_users_query(hackathon_id)).first()[0]

        query = conn.execute(
            table.select()
                .where(where_clause).order_by(*order_clause)
                .offset(offset).limit(limit).reduce_columns())

        for row in query.fetchall():
            user = {
                "user_id": row["user_id"],
                "username": row["username"],
                "level": row["player_level"],
                "organization_id": row["organization_id"],
                "organization": row["organization_name"],
                "version_number": int(row["num_submissions"]),
                "num_games": int(row["num_games"]),
                "score": float(row["score"]),
                "language": row["language"],
                "global_rank": int(row["global_rank"])
                if row["global_rank"] is not None else None,
                "local_rank": int(row["local_rank"])
                if row["local_rank"] is not None else None,
            }

            if total_users and row["global_rank"] is not None:
                user["global_tier"] = util.tier(
                    row["global_rank"], total_users)
            else:
                user["global_tier"] = None

            if hackathon_users and row["local_rank"] is not None:
                user["local_tier"] = util.tier(
                    row["local_rank"], hackathon_users)
            else:
                user["local_tier"] = None

            result.append(user)

        return flask.jsonify(result)