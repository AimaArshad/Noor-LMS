"""Integration tests for quizzes & attempts (needs the PostgreSQL test database)."""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import and_, func, select, update

from app.models import (
    Quiz,
    QuizAnswer,
    QuizAttempt,
    QuizOption,
    QuizQuestion,
    TodoItem,
    TodoRefType,
)
from tests.helpers import API, classroom_context, make_user, promote_to_admin, user_id

pytestmark = pytest.mark.asyncio

QUIZZES = f"{API}/quizzes"
DUE = "2030-01-01T10:00:00Z"


# ------------------------------------------------------------------ builders
def mcq(prompt: str = "2+2?", points: Any = 2) -> dict[str, Any]:
    return {
        "prompt": prompt,
        "type": "mcq",
        "points": points,
        "options": [{"text": "3"}, {"text": "4", "is_correct": True}, {"text": "5"}],
    }


def true_false(prompt: str = "The sky is blue", points: Any = 1) -> dict[str, Any]:
    return {
        "prompt": prompt,
        "type": "true_false",
        "points": points,
        "options": [{"text": "True", "is_correct": True}, {"text": "False"}],
    }


def short(prompt: str = "Capital of France?", points: Any = 2) -> dict[str, Any]:
    return {
        "prompt": prompt,
        "type": "short_answer",
        "points": points,
        "options": [{"text": "Paris", "is_correct": True}, {"text": "City of Light", "is_correct": True}],
    }


def manual(prompt: str = "Explain gravity", points: Any = 4) -> dict[str, Any]:
    return {"prompt": prompt, "type": "short_answer", "points": points, "options": []}


def quiz_payload(**extra: Any) -> dict[str, Any]:
    return {
        "title": "Quiz 1",
        "published": True,
        "questions": [mcq(), true_false(), short()],  # worth 2 + 1 + 2 = 5 points
        **extra,
    }


# ------------------------------------------------------------------- helpers
def cls_url(ctx: dict[str, Any]) -> str:
    return f"{API}/classrooms/{ctx['cid']}/quizzes"


async def create_quiz(client: AsyncClient, ctx: dict[str, Any], **extra: Any) -> dict[str, Any]:
    resp = await client.post(cls_url(ctx), json=quiz_payload(**extra), headers=ctx["teacher"])
    assert resp.status_code == 201, resp.text
    return resp.json()


async def key(client: AsyncClient, ctx: dict[str, Any], quiz_id: str) -> dict[str, dict[str, Any]]:
    """prompt -> {"id": question id, "options": {text: option id}} (from the teacher view)."""
    data = (await client.get(f"{QUIZZES}/{quiz_id}", headers=ctx["teacher"])).json()
    return {
        q["prompt"]: {"id": q["id"], "options": {o["text"]: o["id"] for o in q["options"]}}
        for q in data["questions"]
    }


def full_marks(k: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"question_id": k["2+2?"]["id"], "selected_option_id": k["2+2?"]["options"]["4"]},
        {"question_id": k["The sky is blue"]["id"], "selected_option_id": k["The sky is blue"]["options"]["True"]},
        {"question_id": k["Capital of France?"]["id"], "answer_text": "paris"},
    ]


async def start(client: AsyncClient, ctx: dict[str, Any], quiz_id: str, who: str = "student") -> Response:
    return await client.post(f"{QUIZZES}/{quiz_id}/start", headers=ctx[who])


async def submit(
    client: AsyncClient, ctx: dict[str, Any], quiz_id: str, answers: list[dict[str, Any]], who: str = "student"
) -> Response:
    return await client.post(f"{QUIZZES}/{quiz_id}/submit", json={"answers": answers}, headers=ctx[who])


async def my_attempt(client: AsyncClient, ctx: dict[str, Any], quiz_id: str, who: str = "student") -> Response:
    return await client.get(f"{QUIZZES}/{quiz_id}/my-attempt", headers=ctx[who])


async def count(session_maker: Any, model: Any, *where: Any) -> int:  # noqa: ANN401
    async with session_maker() as s:
        return await s.scalar(select(func.count()).select_from(model).where(*where)) or 0


async def shift_start(session_maker: Any, quiz_id: str, minutes: int) -> None:  # noqa: ANN401
    """Pretend the attempts started ``minutes`` earlier."""
    async with session_maker() as s:
        await s.execute(
            update(QuizAttempt)
            .where(QuizAttempt.quiz_id == uuid.UUID(quiz_id))
            .values(started_at=QuizAttempt.started_at - timedelta(minutes=minutes))
        )
        await s.commit()


def quiz_ref(quiz_id: str) -> Any:  # noqa: ANN401
    return and_(TodoItem.ref_type == TodoRefType.QUIZ, TodoItem.ref_id == uuid.UUID(quiz_id))


# ------------------------------------------------------------------- create
async def test_create_with_nested_questions_and_validation(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    resp = await client.post(
        cls_url(ctx), json=quiz_payload(time_limit_minutes=30, due_at=DUE), headers=ctx["teacher"]
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["view"] == "teacher" and body["published"] is True and body["allow_retake"] is False
    assert body["time_limit_minutes"] == 30 and body["classroom_id"] == str(ctx["cid"])
    assert [q["order_index"] for q in body["questions"]] == [0, 1, 2]
    first = body["questions"][0]
    assert first["points"] == 2
    assert [o["text"] for o in first["options"]] == ["3", "4", "5"]  # author's order is kept
    assert [o["is_correct"] for o in first["options"]] == [False, True, False]

    teacher = ctx["teacher"]
    no_correct = {"prompt": "x", "type": "mcq", "options": [{"text": "a"}, {"text": "b"}]}
    assert (await client.post(cls_url(ctx), json=quiz_payload(questions=[no_correct]), headers=teacher)).status_code == 422
    assert (await client.post(cls_url(ctx), json=quiz_payload(questions=[]), headers=teacher)).status_code == 422  # published, empty
    assert (await client.post(cls_url(ctx), json=quiz_payload(title="  "), headers=teacher)).status_code == 422
    assert (await client.post(cls_url(ctx), json=quiz_payload(classroom_id=str(uuid.uuid4())), headers=teacher)).status_code == 422
    too_big = [mcq(f"q{i}", points="9999.99") for i in range(11)]
    assert (await client.post(cls_url(ctx), json=quiz_payload(questions=too_big), headers=teacher)).status_code == 422

    draft = await client.post(cls_url(ctx), json={"title": "Empty draft"}, headers=teacher)
    assert draft.status_code == 201 and draft.json()["published"] is False and draft.json()["questions"] == []


async def test_only_classroom_teachers_create(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    payload = quiz_payload()
    assert (await client.post(cls_url(ctx), json=payload, headers=ctx["student"])).status_code == 403
    assert (await client.post(cls_url(ctx), json=payload, headers=ctx["outsider"])).status_code == 404
    assert (await client.post(cls_url(ctx), json=payload)).status_code == 401


# --------------------------------------------------------------- visibility
async def test_student_view_hides_the_answer_key_and_drafts(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    draft = await create_quiz(client, ctx, published=False, title="Draft")
    live = await create_quiz(client, ctx, title="Live")

    student_list = (await client.get(cls_url(ctx), headers=ctx["student"])).json()
    assert [q["title"] for q in student_list["items"]] == ["Live"] and student_list["total"] == 1
    teacher_list = (await client.get(cls_url(ctx), headers=ctx["teacher"])).json()
    assert {q["title"] for q in teacher_list["items"]} == {"Draft", "Live"}
    only_drafts = (await client.get(cls_url(ctx), params={"published": "false"}, headers=ctx["teacher"])).json()
    assert [q["title"] for q in only_drafts["items"]] == ["Draft"]
    assert (await client.get(cls_url(ctx), headers=ctx["outsider"])).status_code == 404

    assert (await client.get(f"{QUIZZES}/{draft['id']}", headers=ctx["student"])).status_code == 404
    assert (await client.get(f"{QUIZZES}/{draft['id']}", headers=ctx["teacher"])).status_code == 200
    assert (await client.get(f"{QUIZZES}/{live['id']}", headers=ctx["outsider"])).status_code == 404
    assert (await client.get(f"{QUIZZES}/{live['id']}")).status_code == 401
    assert (await client.get(f"{QUIZZES}/{uuid.uuid4()}", headers=ctx["teacher"])).status_code == 404

    teacher_view = (await client.get(f"{QUIZZES}/{live['id']}", headers=ctx["teacher"])).json()
    assert teacher_view["view"] == "teacher"
    assert teacher_view["questions"][0]["options"][1]["is_correct"] is True

    raw = await client.get(f"{QUIZZES}/{live['id']}", headers=ctx["student"])
    assert raw.status_code == 200
    assert "is_correct" not in raw.text and "Paris" not in raw.text  # no key, no accepted answers
    view = json.loads(raw.text)
    assert view["view"] == "student" and len(view["questions"]) == 3
    short_q = next(q for q in view["questions"] if q["type"] == "short_answer")
    assert short_q["options"] == []
    mcq_q = next(q for q in view["questions"] if q["type"] == "mcq")
    assert [o["text"] for o in mcq_q["options"]] == ["3", "4", "5"]
    assert all(set(o) == {"id", "text"} for o in mcq_q["options"])


# -------------------------------------------------------------------- todos
async def test_publish_syncs_todo_items(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    teacher = ctx["teacher"]
    draft = await create_quiz(client, ctx, published=False)
    url = f"{QUIZZES}/{draft['id']}"
    assert await count(session_maker, TodoItem, quiz_ref(draft["id"])) == 0

    # draft needs questions before it can be published
    assert (await client.patch(url, json={"published": True}, headers=teacher)).status_code == 200  # has 3 questions

    assert await count(session_maker, TodoItem, quiz_ref(draft["id"])) == 2  # Sam + Cleo, not the teacher
    await client.patch(url, json={"due_at": DUE}, headers=teacher)
    async with session_maker() as s:
        todos = (await s.scalars(select(TodoItem).where(quiz_ref(draft["id"])))).all()
        assert {t.user_id for t in todos} == {await user_id(client, ctx["student"]), await user_id(client, ctx["classmate"])}
        assert all(t.title == "Quiz 1" and t.due_at is not None and not t.is_done for t in todos)

    await client.patch(url, json={"published": True}, headers=teacher)  # idempotent
    assert await count(session_maker, TodoItem, quiz_ref(draft["id"])) == 2

    await client.patch(url, json={"title": "Renamed"}, headers=teacher)
    async with session_maker() as s:
        assert set((await s.scalars(select(TodoItem.title).where(quiz_ref(draft["id"])))).all()) == {"Renamed"}

    assert (await client.patch(url, json={"published": False}, headers=teacher)).status_code == 200
    assert await count(session_maker, TodoItem, quiz_ref(draft["id"])) == 0

    direct = await create_quiz(client, ctx)  # created already published
    assert await count(session_maker, TodoItem, quiz_ref(direct["id"])) == 2
    assert (await client.delete(f"{QUIZZES}/{direct['id']}", headers=teacher)).status_code == 204
    assert await count(session_maker, TodoItem, quiz_ref(direct["id"])) == 0


# ------------------------------------------------------------------- update
async def test_update_rules(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    teacher = ctx["teacher"]
    quiz = await create_quiz(client, ctx)
    url = f"{QUIZZES}/{quiz['id']}"

    assert (await client.patch(url, json={"title": "X"}, headers=ctx["student"])).status_code == 403
    assert (await client.patch(url, json={"title": "X"}, headers=ctx["outsider"])).status_code == 404
    assert (await client.patch(url, json={}, headers=teacher)).status_code == 422
    assert (await client.patch(url, json={"title": None}, headers=teacher)).status_code == 422
    assert (await client.patch(url, json={"published": None}, headers=teacher)).status_code == 422
    assert (await client.patch(url, json={"allow_retake": None}, headers=teacher)).status_code == 422

    ok = await client.patch(
        url,
        json={"title": " New ", "time_limit_minutes": 15, "allow_retake": True, "description": "  "},
        headers=teacher,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["title"] == "New" and ok.json()["time_limit_minutes"] == 15
    assert ok.json()["allow_retake"] is True and ok.json()["description"] is None

    replaced = await client.patch(url, json={"questions": [mcq("New question", 3)]}, headers=teacher)
    assert replaced.status_code == 200
    assert [q["prompt"] for q in replaced.json()["questions"]] == ["New question"]

    # a published quiz cannot end up without questions; the failed request changes nothing
    assert (await client.patch(url, json={"questions": []}, headers=teacher)).status_code == 422
    assert len((await client.get(url, headers=teacher)).json()["questions"]) == 1

    # once somebody has started, questions and publish state are locked
    assert (await start(client, ctx, quiz["id"])).status_code == 201
    assert (await client.patch(url, json={"questions": [mcq()]}, headers=teacher)).status_code == 409
    assert (await client.patch(url, json={"published": False}, headers=teacher)).status_code == 409
    assert (await client.patch(url, json={"title": "Still editable"}, headers=teacher)).status_code == 200


# ------------------------------------------------------------- attempt flow
async def test_start_submit_and_no_retake(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    quiz = await create_quiz(client, ctx)
    k = await key(client, ctx, quiz["id"])

    empty = (await my_attempt(client, ctx, quiz["id"])).json()
    assert empty == {"attempt": None, "attempts_used": 0, "can_start": True}

    first = await start(client, ctx, quiz["id"])
    assert first.status_code == 201, first.text
    started = first.json()
    assert started["quiz_id"] == quiz["id"] and started["expires_at"] is None
    assert started["quiz"]["view"] == "student" and "is_correct" not in first.text

    again = await start(client, ctx, quiz["id"])  # resume, same attempt
    assert again.status_code == 200 and again.json()["attempt_id"] == started["attempt_id"]

    open_attempt = (await my_attempt(client, ctx, quiz["id"])).json()
    assert open_attempt["attempts_used"] == 1 and open_attempt["can_start"] is True
    assert open_attempt["attempt"]["submitted_at"] is None and open_attempt["attempt"]["answers"] == []

    resp = await submit(client, ctx, quiz["id"], full_marks(k))
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["id"] == started["attempt_id"] and result["submitted_at"]
    assert result["score"] == 5 and result["max_score"] == 5 and result["pending_manual_grading"] is False
    assert result["student"] is None
    assert len(result["answers"]) == 3 and all(a["is_correct"] for a in result["answers"])
    assert [a["points_awarded"] for a in result["answers"]] == [2, 1, 2]  # quiz order
    assert k["2+2?"]["options"]["3"] not in resp.text  # the answer key is not revealed

    assert (await start(client, ctx, quiz["id"])).status_code == 409  # no retake
    assert (await submit(client, ctx, quiz["id"], [])).status_code == 409  # nothing open any more
    done = (await my_attempt(client, ctx, quiz["id"])).json()
    assert done["can_start"] is False and done["attempts_used"] == 1 and done["attempt"]["score"] == 5


async def test_concurrent_starts_create_one_attempt(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    quiz = await create_quiz(client, ctx)
    first, second = await asyncio.gather(
        start(client, ctx, quiz["id"]), start(client, ctx, quiz["id"])
    )
    assert sorted([first.status_code, second.status_code]) == [200, 201]
    assert first.json()["attempt_id"] == second.json()["attempt_id"]
    assert await count(session_maker, QuizAttempt, QuizAttempt.quiz_id == uuid.UUID(quiz["id"])) == 1


async def test_grading_details(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    quiz = await create_quiz(client, ctx)
    k = await key(client, ctx, quiz["id"])
    await start(client, ctx, quiz["id"])

    answers = [
        {"question_id": k["2+2?"]["id"], "selected_option_id": k["2+2?"]["options"]["3"]},  # wrong
        # true/false question left out
        {"question_id": k["Capital of France?"]["id"], "answer_text": "  city  of   LIGHT "},  # accepted
    ]
    result = (await submit(client, ctx, quiz["id"], answers)).json()
    assert result["score"] == 2
    by_q = {a["question_id"]: a for a in result["answers"]}
    assert len(by_q) == 3  # one result row per question, answered or not
    assert by_q[k["2+2?"]["id"]]["is_correct"] is False and by_q[k["2+2?"]["id"]]["points_awarded"] == 0
    tf = by_q[k["The sky is blue"]["id"]]
    assert tf["is_correct"] is False and tf["points_awarded"] == 0 and tf["selected_option_id"] is None
    sa = by_q[k["Capital of France?"]["id"]]
    assert sa["is_correct"] is True and sa["answer_text"] == "city  of   LIGHT"


async def test_submit_validation_and_roles(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    quiz = await create_quiz(client, ctx)
    draft = await create_quiz(client, ctx, published=False, title="Draft")
    k = await key(client, ctx, quiz["id"])
    q_mcq, q_tf, q_short = k["2+2?"], k["The sky is blue"], k["Capital of France?"]

    assert (await submit(client, ctx, quiz["id"], [])).status_code == 409  # not started yet
    await start(client, ctx, quiz["id"])

    bad_bodies = [
        [{"question_id": str(uuid.uuid4()), "answer_text": "x"}],  # unknown question
        [{"question_id": q_mcq["id"], "answer_text": "4"}],  # text for a choice question
        [{"question_id": q_mcq["id"], "selected_option_id": q_tf["options"]["True"]}],  # foreign option
        [{"question_id": q_short["id"], "selected_option_id": q_mcq["options"]["4"]}],  # option for short answer
        [{"question_id": q_mcq["id"]}],  # no answer at all
        [
            {"question_id": q_mcq["id"], "selected_option_id": q_mcq["options"]["4"]},
            {"question_id": q_mcq["id"], "selected_option_id": q_mcq["options"]["3"]},
        ],  # duplicate question
        [{"question_id": q_mcq["id"], "selected_option_id": q_mcq["options"]["4"], "is_correct": True}],  # extra field
    ]
    for body in bad_bodies:
        assert (await submit(client, ctx, quiz["id"], body)).status_code == 422, body

    # failed submissions did not consume the attempt
    assert (await submit(client, ctx, quiz["id"], full_marks(k))).status_code == 200

    assert (await start(client, ctx, quiz["id"], "teacher")).status_code == 403
    assert (await submit(client, ctx, quiz["id"], [], "teacher")).status_code == 403
    assert (await my_attempt(client, ctx, quiz["id"], "teacher")).status_code == 403
    assert (await start(client, ctx, quiz["id"], "outsider")).status_code == 404
    assert (await start(client, ctx, draft["id"])).status_code == 404  # students cannot start drafts
    assert (await client.post(f"{QUIZZES}/{quiz['id']}/start")).status_code == 401


# --------------------------------------------------------------- time limit
async def test_time_limit_is_enforced(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)

    on_time = await create_quiz(client, ctx, time_limit_minutes=30, title="On time")
    s = (await start(client, ctx, on_time["id"])).json()
    started, expires = datetime.fromisoformat(s["started_at"]), datetime.fromisoformat(s["expires_at"])
    assert expires - started == timedelta(minutes=30)
    await shift_start(session_maker, on_time["id"], 29)
    assert (await submit(client, ctx, on_time["id"], [])).status_code == 200  # still inside the limit

    late = await create_quiz(client, ctx, time_limit_minutes=30, title="Late")
    await start(client, ctx, late["id"])
    await shift_start(session_maker, late["id"], 31)
    rejected = await submit(client, ctx, late["id"], [])
    assert rejected.status_code == 409 and "time limit" in rejected.json()["error"]["message"].lower()

    status_after = (await my_attempt(client, ctx, late["id"])).json()  # auto-closed with score 0
    assert status_after["attempt"]["submitted_at"] is not None and status_after["attempt"]["score"] == 0
    assert status_after["can_start"] is False and status_after["attempts_used"] == 1
    assert (await start(client, ctx, late["id"])).status_code == 409  # no retake allowed


async def test_expired_attempt_does_not_block_a_retake(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    quiz = await create_quiz(client, ctx, time_limit_minutes=10, allow_retake=True)
    first = (await start(client, ctx, quiz["id"])).json()
    await shift_start(session_maker, quiz["id"], 20)

    second = await start(client, ctx, quiz["id"])  # the expired attempt is closed, a new one begins
    assert second.status_code == 201 and second.json()["attempt_id"] != first["attempt_id"]
    assert (await my_attempt(client, ctx, quiz["id"])).json()["attempts_used"] == 2


# ------------------------------------------------------------------ retakes
async def test_retake_and_best_score_average(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    quiz = await create_quiz(client, ctx, allow_retake=True)
    k = await key(client, ctx, quiz["id"])

    first = (await start(client, ctx, quiz["id"])).json()
    assert (await submit(client, ctx, quiz["id"], [])).json()["score"] == 0

    second = await start(client, ctx, quiz["id"])
    assert second.status_code == 201 and second.json()["attempt_id"] != first["attempt_id"]
    assert (await submit(client, ctx, quiz["id"], full_marks(k))).json()["score"] == 5

    mine = (await my_attempt(client, ctx, quiz["id"])).json()
    assert mine["attempts_used"] == 2 and mine["can_start"] is True and mine["attempt"]["score"] == 5

    results = (await client.get(f"{QUIZZES}/{quiz['id']}/results", headers=ctx["teacher"])).json()
    assert results["attempt_count"] == 2 and results["submitted_count"] == 2
    assert results["average_score"] == 5  # best score per student, not the mean of both attempts
    assert [a["score"] for a in results["attempts"]] == [5, 0]  # newest attempt first


# ------------------------------------------------------------------ results
async def test_teacher_results(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    quiz = await create_quiz(client, ctx)
    k = await key(client, ctx, quiz["id"])
    url = f"{QUIZZES}/{quiz['id']}/results"

    nothing = (await client.get(url, headers=ctx["teacher"])).json()
    assert nothing["attempt_count"] == 0 and nothing["average_score"] is None
    assert nothing["not_attempted_count"] == 2 and nothing["max_score"] == 5

    await start(client, ctx, quiz["id"])
    await submit(client, ctx, quiz["id"], full_marks(k))  # Sam: 5
    partial = [{"question_id": k["2+2?"]["id"], "selected_option_id": k["2+2?"]["options"]["4"]}]
    await start(client, ctx, quiz["id"], "classmate")
    await submit(client, ctx, quiz["id"], partial, "classmate")  # Cleo: 2

    data = (await client.get(url, headers=ctx["teacher"])).json()
    assert data["attempt_count"] == 2 and data["submitted_count"] == 2 and data["not_attempted_count"] == 0
    assert data["average_score"] == 3.5 and data["max_score"] == 5
    assert [a["student"]["full_name"] for a in data["attempts"]] == ["Cleo", "Sam"]
    assert all("email" not in a["student"] for a in data["attempts"])
    assert [a["score"] for a in data["attempts"]] == [2, 5]

    page = (await client.get(url, params={"limit": 1, "offset": 1}, headers=ctx["teacher"])).json()
    assert page["attempt_count"] == 2 and [a["student"]["full_name"] for a in page["attempts"]] == ["Sam"]
    assert (await client.get(url, params={"limit": 0}, headers=ctx["teacher"])).status_code == 422

    assert (await client.get(url, headers=ctx["student"])).status_code == 403
    assert (await client.get(url, headers=ctx["outsider"])).status_code == 404
    assert (await client.get(url)).status_code == 401


# ----------------------------------------------------------- manual grading
async def test_manual_grading_of_short_answers(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    teacher = ctx["teacher"]
    quiz = await create_quiz(client, ctx, title="Essay", questions=[manual()])
    k = await key(client, ctx, quiz["id"])
    qid = k["Explain gravity"]["id"]

    started = (await start(client, ctx, quiz["id"])).json()
    result = (
        await submit(client, ctx, quiz["id"], [{"question_id": qid, "answer_text": "Mass bends spacetime"}])
    ).json()
    assert result["score"] == 0 and result["pending_manual_grading"] is True
    assert result["answers"][0]["is_correct"] is None and result["answers"][0]["points_awarded"] is None

    url = f"{QUIZZES}/{quiz['id']}/attempts/{started['attempt_id']}/answers/{qid}"
    assert (await client.patch(url, json={"points_awarded": 3}, headers=ctx["student"])).status_code == 403
    assert (await client.patch(url, json={"points_awarded": 3}, headers=ctx["outsider"])).status_code == 404
    assert (await client.patch(url, json={"points_awarded": 5}, headers=teacher)).status_code == 422  # worth 4
    assert (await client.patch(url, json={"points_awarded": -1}, headers=teacher)).status_code == 422
    unknown = f"{QUIZZES}/{quiz['id']}/attempts/{started['attempt_id']}/answers/{uuid.uuid4()}"
    assert (await client.patch(unknown, json={"points_awarded": 1}, headers=teacher)).status_code == 404

    graded = await client.patch(url, json={"points_awarded": 3}, headers=teacher)
    assert graded.status_code == 200, graded.text
    g = graded.json()
    assert g["score"] == 3 and g["pending_manual_grading"] is False and g["student"]["full_name"] == "Sam"
    assert g["answers"][0]["points_awarded"] == 3 and g["answers"][0]["is_correct"] is False  # partial credit

    assert (await my_attempt(client, ctx, quiz["id"])).json()["attempt"]["score"] == 3
    full = await client.patch(url, json={"points_awarded": 4}, headers=teacher)
    assert full.json()["score"] == 4 and full.json()["answers"][0]["is_correct"] is True


async def test_cannot_grade_an_open_attempt(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    quiz = await create_quiz(client, ctx, questions=[manual()])
    k = await key(client, ctx, quiz["id"])
    started = (await start(client, ctx, quiz["id"])).json()
    url = f"{QUIZZES}/{quiz['id']}/attempts/{started['attempt_id']}/answers/{k['Explain gravity']['id']}"
    assert (await client.patch(url, json={"points_awarded": 1}, headers=ctx["teacher"])).status_code == 409


# ----------------------------------------------------------------- archived
async def test_archived_classroom_is_read_only(client: AsyncClient) -> None:
    ctx = await classroom_context(client)
    teacher = ctx["teacher"]
    quiz = await create_quiz(client, ctx)
    other = await create_quiz(client, ctx, title="Other")
    await start(client, ctx, quiz["id"])  # an attempt is open when the classroom gets archived
    await client.patch(f"{API}/classrooms/{ctx['cid']}", json={"is_archived": True}, headers=teacher)

    assert (await client.post(cls_url(ctx), json=quiz_payload(), headers=teacher)).status_code == 403
    assert (await client.patch(f"{QUIZZES}/{quiz['id']}", json={"title": "x"}, headers=teacher)).status_code == 403
    assert (await client.delete(f"{QUIZZES}/{quiz['id']}", headers=teacher)).status_code == 403
    assert (await start(client, ctx, other["id"])).status_code == 403
    assert (await submit(client, ctx, quiz["id"], [])).status_code == 403
    assert (await client.get(cls_url(ctx), headers=ctx["student"])).status_code == 200  # reads still work
    assert (await client.get(f"{QUIZZES}/{quiz['id']}/results", headers=teacher)).status_code == 200
    assert (await my_attempt(client, ctx, quiz["id"])).json()["can_start"] is False

    await client.patch(f"{API}/classrooms/{ctx['cid']}", json={"is_archived": False}, headers=teacher)
    assert (await submit(client, ctx, quiz["id"], [])).status_code == 200


# ------------------------------------------------------------------- delete
async def test_delete_cascades(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    quiz = await create_quiz(client, ctx)
    k = await key(client, ctx, quiz["id"])
    await start(client, ctx, quiz["id"])
    await submit(client, ctx, quiz["id"], full_marks(k))
    url = f"{QUIZZES}/{quiz['id']}"

    assert (await client.delete(url, headers=ctx["student"])).status_code == 403
    assert (await client.delete(url, headers=ctx["outsider"])).status_code == 404
    assert (await client.delete(url, headers=ctx["teacher"])).status_code == 204
    assert (await client.get(url, headers=ctx["teacher"])).status_code == 404
    assert (await client.delete(url, headers=ctx["teacher"])).status_code == 404

    for model in (Quiz, QuizQuestion, QuizOption, QuizAttempt, QuizAnswer):
        assert await count(session_maker, model) == 0, model
    assert await count(session_maker, TodoItem, quiz_ref(quiz["id"])) == 0


# -------------------------------------------------------------------- admin
async def test_admin_manages_but_cannot_take_quizzes(client: AsyncClient, session_maker) -> None:  # noqa: ANN001
    ctx = await classroom_context(client)
    admin = await make_user(client, "root@example.com")
    await promote_to_admin(session_maker, "root@example.com")

    created = await client.post(cls_url(ctx), json=quiz_payload(title="By admin"), headers=admin)
    assert created.status_code == 201, created.text
    qid = created.json()["id"]
    assert (await client.get(f"{QUIZZES}/{qid}/results", headers=admin)).status_code == 200
    assert (await client.get(f"{QUIZZES}/{qid}", headers=admin)).json()["view"] == "teacher"
    assert (await client.post(f"{QUIZZES}/{qid}/start", headers=admin)).status_code == 403