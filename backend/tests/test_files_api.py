"""Integration tests for /files (needs the PostgreSQL test database)."""

import io
import uuid
import zipfile
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1.routers.files import get_storage_backend
from app.core.config import settings
from app.main import app
from app.models import Assignment, AssignmentState, Material, Submission, User
from app.schemas.common import AttachmentRef
from app.services.file_service import FileService
from app.services.storage import LocalStorage

pytestmark = pytest.mark.asyncio

PASSWORD = "Passw0rdX"
UPLOAD = "/api/v1/files/upload"
FILES = "/api/v1/files"
CLASSROOMS = "/api/v1/classrooms"


def _zip(*names: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for name in names or ("hello.txt",):
            archive.writestr(name, "x")
    return buf.getvalue()


PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 24
GIF = b"GIF89a" + b"\x00" * 24
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 24
WAV = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 24
MP3 = b"ID3\x03\x00" + b"\x00" * 24
ZIP = _zip()
DOCX = _zip("[Content_Types].xml", "word/document.xml")
PPTX = _zip("[Content_Types].xml", "ppt/presentation.xml")
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


# ------------------------------------------------------------------ fixtures
@pytest_asyncio.fixture
async def storage(client: AsyncClient, tmp_path: Path) -> LocalStorage:
    """Per-test storage directory (the `client` fixture clears the override afterwards)."""
    backend = LocalStorage(tmp_path / "uploads")
    app.dependency_overrides[get_storage_backend] = lambda: backend
    return backend


async def make_user(client: AsyncClient, email: str, role: str = "student") -> dict[str, str]:
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": email.split("@")[0].title(), "role": role},
    )
    assert reg.status_code == 201, reg.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def user_id(client: AsyncClient, headers: dict[str, str]) -> uuid.UUID:
    return uuid.UUID((await client.get("/api/v1/auth/me", headers=headers)).json()["id"])


async def upload(
    client: AsyncClient,
    headers: dict[str, str],
    name: str = "doc.pdf",
    data: bytes = PDF,
    content_type: str = "application/pdf",
):  # noqa: ANN201
    return await client.post(UPLOAD, files={"file": (name, data, content_type)}, headers=headers)


def attachments(file_json: dict) -> list[dict]:
    return [
        {"file_id": file_json["id"], "name": file_json["original_name"], "mime_type": file_json["mime_type"]}
    ]


async def classroom_context(client: AsyncClient) -> dict:
    teacher = await make_user(client, "tina@example.com", "teacher")
    student = await make_user(client, "sam@example.com")
    classmate = await make_user(client, "cleo@example.com")
    outsider = await make_user(client, "olga@example.com")
    classroom = (await client.post(CLASSROOMS, json={"name": "Math"}, headers=teacher)).json()
    for headers in (student, classmate):
        joined = await client.post(
            f"{CLASSROOMS}/join", json={"join_code": classroom["join_code"]}, headers=headers
        )
        assert joined.status_code == 200
    return {
        "teacher": teacher,
        "student": student,
        "classmate": classmate,
        "outsider": outsider,
        "cid": uuid.UUID(classroom["id"]),
    }


# ------------------------------------------------------------------- upload
async def test_upload_and_download_pdf(client: AsyncClient, storage: LocalStorage) -> None:
    headers = await make_user(client, "sam@example.com")
    resp = await upload(client, headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["original_name"] == "doc.pdf" and body["mime_type"] == "application/pdf"
    assert body["size_bytes"] == len(PDF)
    assert body["download_url"] == f"/api/v1/files/{body['id']}"
    assert "path" not in body and "stored_name" not in body

    stored = [p for p in storage.root.rglob("*") if p.is_file()]
    assert len(stored) == 1 and stored[0].suffix == ".pdf" and stored[0].name != "doc.pdf"

    dl = await client.get(body["download_url"], headers=headers)
    assert dl.status_code == 200 and dl.content == PDF
    assert dl.headers["content-type"] == "application/pdf"
    assert dl.headers["content-disposition"].startswith("inline")
    assert dl.headers["x-content-type-options"] == "nosniff"
    assert dl.headers["accept-ranges"] == "bytes"

    forced = await client.get(body["download_url"], params={"download": "true"}, headers=headers)
    assert forced.headers["content-disposition"].startswith("attachment")


@pytest.mark.parametrize(
    ("name", "data", "mime"),
    [
        ("a.png", PNG, "image/png"),
        ("a.jpg", JPG, "image/jpeg"),
        ("a.jpeg", JPG, "image/jpeg"),
        ("a.gif", GIF, "image/gif"),
        ("a.webp", WEBP, "image/webp"),
        ("a.mp3", MP3, "audio/mpeg"),
        ("a.wav", WAV, "audio/wav"),
        ("a.txt", "héllo wörld\n".encode(), "text/plain"),
        ("a.docx", DOCX, DOCX_MIME),
        ("a.pptx", PPTX, PPTX_MIME),
        ("a.zip", ZIP, "application/zip"),
        ("UPPER.PNG", PNG, "image/png"),
    ],
)
async def test_all_allowed_types(
    client: AsyncClient, storage: LocalStorage, name: str, data: bytes, mime: str
) -> None:
    headers = await make_user(client, "sam@example.com")
    resp = await upload(client, headers, name, data, "application/octet-stream")
    assert resp.status_code == 201, resp.text
    assert resp.json()["mime_type"] == mime


@pytest.mark.parametrize(
    ("name", "data", "code"),
    [
        ("run.exe", b"MZ\x90\x00", 415),
        ("page.html", b"<script>alert(1)</script>", 415),
        ("pic.svg", b"<svg onload=alert(1)/>", 415),
        ("README", b"hello", 415),
        ("fake.pdf", b"just text, not a pdf", 415),
        ("fake.png", PDF, 415),
        ("fake.docx", ZIP, 415),  # a plain zip is not a Word document
        ("fake.zip", b"not a zip at all", 415),
        ("binary.txt", b"abc\x00def", 415),
        ("empty.txt", b"", 400),
    ],
)
async def test_rejected_uploads(
    client: AsyncClient, storage: LocalStorage, name: str, data: bytes, code: int
) -> None:
    headers = await make_user(client, "sam@example.com")
    resp = await upload(client, headers, name, data, "application/pdf")
    assert resp.status_code == code, resp.text
    assert not [p for p in storage.root.rglob("*") if p.is_file()]  # nothing stored


async def test_client_content_type_is_ignored(client: AsyncClient, storage: LocalStorage) -> None:
    headers = await make_user(client, "sam@example.com")
    resp = await upload(client, headers, "pic.png", PNG, "text/html")
    assert resp.status_code == 201 and resp.json()["mime_type"] == "image/png"


async def test_upload_too_large(
    client: AsyncClient, storage: LocalStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    headers = await make_user(client, "sam@example.com")
    ok = await upload(client, headers, "ok.txt", b"a" * 1024 * 1024, "text/plain")
    assert ok.status_code == 201
    big = await upload(client, headers, "big.txt", b"a" * (1024 * 1024 + 1), "text/plain")
    assert big.status_code == 413


async def test_filename_is_sanitised(client: AsyncClient, storage: LocalStorage) -> None:
    headers = await make_user(client, "sam@example.com")
    resp = await upload(client, headers, "../../etc/evil.txt", b"hi", "text/plain")
    assert resp.status_code == 201 and resp.json()["original_name"] == "evil.txt"
    assert all(storage.root in p.parents for p in storage.root.rglob("*") if p.is_file())


async def test_auth_and_validation(client: AsyncClient, storage: LocalStorage) -> None:
    headers = await make_user(client, "sam@example.com")
    assert (await client.post(UPLOAD, files={"file": ("a.txt", b"x", "text/plain")})).status_code == 401
    assert (await client.get(f"{FILES}/{uuid.uuid4()}")).status_code == 401
    assert (await client.delete(f"{FILES}/{uuid.uuid4()}")).status_code == 401
    assert (await client.post(UPLOAD, headers=headers)).status_code == 422  # no file part
    assert (await client.get(f"{FILES}/{uuid.uuid4()}", headers=headers)).status_code == 404
    assert (await client.get(f"{FILES}/not-a-uuid", headers=headers)).status_code == 422


# ----------------------------------------------------------------- download
async def test_range_requests(client: AsyncClient, storage: LocalStorage) -> None:
    headers = await make_user(client, "sam@example.com")
    meta = (await upload(client, headers, "digits.txt", b"0123456789" * 10, "text/plain")).json()
    url = meta["download_url"]

    first = await client.get(url, headers={**headers, "Range": "bytes=0-3"})
    assert first.status_code == 206 and first.content == b"0123"
    assert first.headers["content-range"] == "bytes 0-3/100" and first.headers["content-length"] == "4"

    tail = await client.get(url, headers={**headers, "Range": "bytes=-5"})
    assert tail.status_code == 206 and tail.content == b"56789"
    assert tail.headers["content-range"] == "bytes 95-99/100"

    open_ended = await client.get(url, headers={**headers, "Range": "bytes=95-"})
    assert open_ended.content == b"56789"

    beyond = await client.get(url, headers={**headers, "Range": "bytes=500-"})
    assert beyond.status_code == 416 and beyond.headers["content-range"] == "bytes */100"

    for header in ("bytes=9-3", "bytes=0-3,5-6", "nonsense"):  # ignored -> whole file
        whole = await client.get(url, headers={**headers, "Range": header})
        assert whole.status_code == 200 and len(whole.content) == 100


async def test_office_files_always_download(client: AsyncClient, storage: LocalStorage) -> None:
    headers = await make_user(client, "sam@example.com")
    meta = (await upload(client, headers, "essay.docx", DOCX, "application/octet-stream")).json()
    resp = await client.get(meta["download_url"], headers=headers)
    assert resp.headers["content-disposition"].startswith("attachment")


async def test_missing_content_on_disk_returns_404(client: AsyncClient, storage: LocalStorage) -> None:
    headers = await make_user(client, "sam@example.com")
    meta = (await upload(client, headers)).json()
    for path in storage.root.rglob("*.pdf"):
        path.unlink()
    assert (await client.get(meta["download_url"], headers=headers)).status_code == 404


# ----------------------------------------------------------- access control
async def test_private_file_is_visible_only_to_uploader(client: AsyncClient, storage: LocalStorage) -> None:
    ctx = await classroom_context(client)
    meta = (await upload(client, ctx["student"])).json()
    assert (await client.get(meta["download_url"], headers=ctx["student"])).status_code == 200
    for who in ("teacher", "classmate", "outsider"):
        assert (await client.get(meta["download_url"], headers=ctx[who])).status_code == 404, who


async def test_assignment_attachment_access(
    client: AsyncClient, storage: LocalStorage, session_maker  # noqa: ANN001
) -> None:
    ctx = await classroom_context(client)
    meta = (await upload(client, ctx["teacher"])).json()
    url = meta["download_url"]

    async with session_maker() as s:
        assignment = Assignment(
            classroom_id=ctx["cid"], title="HW", state=AssignmentState.DRAFT, attachments=attachments(meta)
        )
        s.add(assignment)
        await s.commit()
        assignment_id = assignment.id

    assert (await client.get(url, headers=ctx["teacher"])).status_code == 200
    assert (await client.get(url, headers=ctx["student"])).status_code == 404  # draft is hidden
    assert (await client.get(url, headers=ctx["outsider"])).status_code == 404

    async with session_maker() as s:
        (await s.get(Assignment, assignment_id)).state = AssignmentState.PUBLISHED  # type: ignore[union-attr]
        await s.commit()

    assert (await client.get(url, headers=ctx["student"])).status_code == 200
    assert (await client.get(url, headers=ctx["classmate"])).status_code == 200
    assert (await client.get(url, headers=ctx["outsider"])).status_code == 404


async def test_material_attachment_access(
    client: AsyncClient, storage: LocalStorage, session_maker  # noqa: ANN001
) -> None:
    ctx = await classroom_context(client)
    meta = (await upload(client, ctx["teacher"], "notes.pdf")).json()
    async with session_maker() as s:
        s.add(Material(classroom_id=ctx["cid"], title="Notes", attachments=attachments(meta)))
        await s.commit()
    assert (await client.get(meta["download_url"], headers=ctx["student"])).status_code == 200
    assert (await client.get(meta["download_url"], headers=ctx["outsider"])).status_code == 404


async def test_submission_attachment_access(
    client: AsyncClient, storage: LocalStorage, session_maker  # noqa: ANN001
) -> None:
    ctx = await classroom_context(client)
    meta = (await upload(client, ctx["student"], "answer.docx", DOCX, "application/octet-stream")).json()
    student_id = await user_id(client, ctx["student"])
    async with session_maker() as s:
        assignment = Assignment(classroom_id=ctx["cid"], title="HW", state=AssignmentState.PUBLISHED)
        s.add(assignment)
        await s.flush()
        s.add(Submission(assignment_id=assignment.id, student_id=student_id, attachments=attachments(meta)))
        await s.commit()

    url = meta["download_url"]
    assert (await client.get(url, headers=ctx["student"])).status_code == 200
    assert (await client.get(url, headers=ctx["teacher"])).status_code == 200  # grading
    assert (await client.get(url, headers=ctx["classmate"])).status_code == 404
    assert (await client.get(url, headers=ctx["outsider"])).status_code == 404


# ------------------------------------------------------------------- delete
async def test_delete_rules(
    client: AsyncClient, storage: LocalStorage, session_maker  # noqa: ANN001
) -> None:
    ctx = await classroom_context(client)

    # teacher's file, attached to a published assignment
    t_meta = (await upload(client, ctx["teacher"])).json()
    async with session_maker() as s:
        assignment = Assignment(
            classroom_id=ctx["cid"], title="HW", state=AssignmentState.PUBLISHED, attachments=attachments(t_meta)
        )
        s.add(assignment)
        await s.commit()
        assignment_id = assignment.id
    url = t_meta["download_url"]

    assert (await client.delete(url, headers=ctx["student"])).status_code == 403  # can see it, not the owner
    assert (await client.delete(url, headers=ctx["outsider"])).status_code == 404  # cannot see it
    assert (await client.delete(url, headers=ctx["teacher"])).status_code == 409  # still attached

    async with session_maker() as s:
        (await s.get(Assignment, assignment_id)).attachments = []  # type: ignore[union-attr]
        await s.commit()
    assert (await client.delete(url, headers=ctx["teacher"])).status_code == 204
    assert not [p for p in storage.root.rglob("*") if p.is_file()]
    assert (await client.get(url, headers=ctx["teacher"])).status_code == 404
    assert (await client.delete(url, headers=ctx["teacher"])).status_code == 404

    # a plain private file
    s_meta = (await upload(client, ctx["student"])).json()
    assert (await client.delete(s_meta["download_url"], headers=ctx["classmate"])).status_code == 404
    assert (await client.delete(s_meta["download_url"], headers=ctx["student"])).status_code == 204


# --------------------------------------------------------------- attachments
async def test_resolve_attachments_requires_ownership(
    client: AsyncClient, storage: LocalStorage, session_maker  # noqa: ANN001
) -> None:
    owner_headers = await make_user(client, "owner@example.com")
    await make_user(client, "other@example.com")
    meta = (await upload(client, owner_headers)).json()

    async with session_maker() as s:
        owner = await s.get(User, uuid.UUID(meta["uploader_id"]))
        other = await s.scalar(select(User).where(User.email == "other@example.com"))
        service = FileService(s, storage)
        refs = [AttachmentRef(file_id=meta["id"], name="whatever-the-client-says.pdf")]

        assert await service.resolve_attachments(owner, refs) == [  # type: ignore[arg-type]
            {"file_id": meta["id"], "name": "doc.pdf", "mime_type": "application/pdf"}
        ]
        assert await service.resolve_attachments(owner, []) == []  # type: ignore[arg-type]

        with pytest.raises(HTTPException) as not_owner:
            await service.resolve_attachments(other, refs)  # type: ignore[arg-type]
        assert not_owner.value.status_code == 422

        with pytest.raises(HTTPException) as unknown:
            await service.resolve_attachments(owner, [AttachmentRef(file_id=uuid.uuid4(), name="x.pdf")])  # type: ignore[arg-type]
        assert unknown.value.status_code == 422