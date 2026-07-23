# Stage 2B Attachment and Local Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move attachments to the existing backend SQLite BLOB store, retain only password-based backup encryption in the browser, and remove Dexie/IndexedDB from the frontend.

**Architecture:** FastAPI owns attachment validation, metadata, binary content, and deletion through a focused router/service pair. The React client stores only attachment IDs in transactions and after-sales records, renders backend content URLs, and uses a separate stateless `backupCrypto.ts` utility for encrypted JSON backups.

**Tech Stack:** FastAPI, SQLAlchemy async, SQLite BLOB, React 18, TypeScript, Vitest, Web Crypto API, Docker Compose.

---

## File map

- Create `server/backend/app/services/attachment_service.py`: attachment persistence operations and constants.
- Create `server/backend/app/routers/attachments.py`: upload, batch metadata, content, and delete HTTP boundary.
- Create `server/backend/test_attachment_routes.py`: real in-memory SQLite route tests.
- Modify `server/backend/app/schemas.py`: attachment metadata and batch request schemas.
- Modify `server/backend/app/main.py`: register attachment router.
- Modify `src/services/apiClient.ts`: multipart request and canonical API URL support.
- Modify `tests/mockApiClient.ts`: mirror the new client surface for service tests.
- Rewrite `src/services/attachmentService.ts`: backend-only attachment adapter.
- Create `tests/services/attachmentService.test.ts`: frontend adapter tests.
- Modify `src/components/AttachmentUpload.tsx`: render backend content URLs instead of object URLs.
- Modify `src/types/index.ts`: attachment metadata no longer contains a browser Blob.
- Create `src/utils/backupCrypto.ts`: password-derived JSON backup encryption only.
- Create `tests/utils/backupCrypto.test.ts`: encryption format and failure tests.
- Modify `src/utils/export.ts` and `src/pages/Settings.tsx`: import the focused backup utility.
- Delete `src/utils/crypto.ts`: obsolete field encryption and IndexedDB key store.
- Extend `tests/utils/backendDataBoundary.test.ts`: enforce the no-Dexie boundary.
- Delete `src/db/index.ts` and unused `tests/helpers.ts`.
- Modify `tests/setup.ts`, `package.json`, and `package-lock.json`: remove fake IndexedDB and Dexie dependencies.

### Task 1: Add the backend attachment API

**Files:**
- Create: `server/backend/test_attachment_routes.py`
- Create: `server/backend/app/services/attachment_service.py`
- Create: `server/backend/app/routers/attachments.py`
- Modify: `server/backend/app/schemas.py`
- Modify: `server/backend/app/main.py`

- [ ] **Step 1: Write failing route tests**

Create `server/backend/test_attachment_routes.py` using the same in-memory database override as `test_product_template_routes.py`. Include these behaviors:

```python
import unittest

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app


class AttachmentRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(bind=self.engine, expire_on_commit=False)

        async def override_get_db():
            async with self.Session() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

    async def asyncTearDown(self):
        app.dependency_overrides.pop(get_db, None)
        await self.engine.dispose()

    async def test_upload_batch_content_and_delete(self):
        content = b"fake-png-content"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            uploaded = await client.post(
                "/api/attachments",
                files={"file": ("sample.png", content, "image/png")},
            )
            self.assertEqual(uploaded.status_code, 200)
            metadata = uploaded.json()
            self.assertEqual(metadata["name"], "sample.png")
            self.assertEqual(metadata["size"], len(content))

            batch = await client.post("/api/attachments/batch", json={"ids": [metadata["id"], 9999]})
            self.assertEqual([item["id"] for item in batch.json()], [metadata["id"]])

            downloaded = await client.get(f"/api/attachments/{metadata['id']}/content")
            self.assertEqual(downloaded.status_code, 200)
            self.assertEqual(downloaded.content, content)
            self.assertEqual(downloaded.headers["content-type"], "image/png")

            deleted = await client.delete(f"/api/attachments/{metadata['id']}")
            self.assertEqual(deleted.status_code, 200)
            missing = await client.get(f"/api/attachments/{metadata['id']}/content")
            self.assertEqual(missing.status_code, 404)

    async def test_upload_rejects_disallowed_mime(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/attachments",
                files={"file": ("notes.txt", b"text", "text/plain")},
            )
        self.assertEqual(response.status_code, 400)

    async def test_upload_rejects_empty_and_oversized_files(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            empty = await client.post(
                "/api/attachments",
                files={"file": ("empty.png", b"", "image/png")},
            )
            oversized = await client.post(
                "/api/attachments",
                files={"file": ("large.png", b"x" * (5 * 1024 * 1024 + 1), "image/png")},
            )
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(oversized.status_code, 413)
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
python -m pytest server/backend/test_attachment_routes.py -q
```

Expected: failures with 404 because `/api/attachments` is not registered.

- [ ] **Step 3: Implement the persistence service and schemas**

Add to `server/backend/app/schemas.py`:

```python
class AttachmentOut(ORMBase):
    id: int
    name: str
    type: str
    size: int
    created_at: datetime


class AttachmentBatchRequest(BaseModel):
    ids: List[int] = Field(default_factory=list, max_length=50)
```

Create `server/backend/app/services/attachment_service.py`:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Attachment

MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024
ACCEPTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


async def create_attachment(db: AsyncSession, *, name: str, content_type: str, content: bytes) -> Attachment:
    attachment = Attachment(name=name, type=content_type, size=len(content), blob=content)
    db.add(attachment)
    await db.flush()
    await db.refresh(attachment)
    return attachment


async def get_attachment(db: AsyncSession, attachment_id: int) -> Attachment | None:
    return await db.get(Attachment, attachment_id)


async def get_attachments(db: AsyncSession, ids: list[int]) -> list[Attachment]:
    if not ids:
        return []
    items = list((await db.execute(select(Attachment).where(Attachment.id.in_(ids)))).scalars().all())
    by_id = {item.id: item for item in items}
    return [by_id[item_id] for item_id in ids if item_id in by_id]


async def delete_attachment(db: AsyncSession, attachment: Attachment) -> None:
    await db.delete(attachment)
    await db.flush()
```

- [ ] **Step 4: Implement and register the router**

Create `server/backend/app/routers/attachments.py` with:

```python
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import AttachmentBatchRequest, AttachmentOut
from ..services import attachment_service

router = APIRouter(prefix="/api/attachments", tags=["attachments"])


@router.post("", response_model=AttachmentOut)
async def upload_attachment(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    content_type = file.content_type or ""
    if content_type not in attachment_service.ACCEPTED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG/WebP/GIF 图片格式")
    content = await file.read(attachment_service.MAX_ATTACHMENT_SIZE + 1)
    if not content:
        raise HTTPException(status_code=400, detail="附件不能为空")
    if len(content) > attachment_service.MAX_ATTACHMENT_SIZE:
        raise HTTPException(status_code=413, detail="附件大小不能超过 5MB")
    name = Path((file.filename or "attachment").replace("\\", "/")).name[:255] or "attachment"
    attachment = await attachment_service.create_attachment(
        db, name=name, content_type=content_type, content=content,
    )
    await db.commit()
    return attachment


@router.post("/batch", response_model=list[AttachmentOut])
async def batch_attachments(payload: AttachmentBatchRequest, db: AsyncSession = Depends(get_db)):
    return await attachment_service.get_attachments(db, payload.ids)


@router.get("/{attachment_id}/content")
async def attachment_content(attachment_id: int, db: AsyncSession = Depends(get_db)):
    attachment = await attachment_service.get_attachment(db, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")
    encoded_name = quote(attachment.name)
    return StreamingResponse(
        BytesIO(attachment.blob),
        media_type=attachment.type,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{encoded_name}"},
    )


@router.delete("/{attachment_id}")
async def remove_attachment(attachment_id: int, db: AsyncSession = Depends(get_db)):
    attachment = await attachment_service.get_attachment(db, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")
    await attachment_service.delete_attachment(db, attachment)
    await db.commit()
    return {"ok": True}
```

Import `attachments` in `server/backend/app/main.py` and add `app.include_router(attachments.router)` beside the other focused routers.

- [ ] **Step 5: Run backend tests and verify GREEN**

Run:

```powershell
python -m pytest server/backend/test_attachment_routes.py -q
python -m pytest server/backend -q
```

Expected: attachment tests pass; full backend suite passes.

- [ ] **Step 6: Commit**

```powershell
git add -- server/backend/app/main.py server/backend/app/schemas.py server/backend/app/routers/attachments.py server/backend/app/services/attachment_service.py server/backend/test_attachment_routes.py
git commit -m "feat: expose backend attachment storage API"
```

### Task 2: Switch the frontend attachment flow to the backend

**Files:**
- Create: `tests/services/attachmentService.test.ts`
- Modify: `tests/mockApiClient.ts`
- Modify: `src/services/apiClient.ts`
- Modify: `src/services/attachmentService.ts`
- Modify: `src/components/AttachmentUpload.tsx`
- Modify: `src/types/index.ts`

- [ ] **Step 1: Write failing frontend service tests**

Create `tests/services/attachmentService.test.ts`:

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getMockCalls, mockApiFactory, resetMockApi, setMockResponse } from '../mockApiClient';

vi.mock('@/services/apiClient', () => mockApiFactory());
import { addAttachment, deleteAttachment, getAttachmentContentUrl, getAttachments } from '@/services/attachmentService';

describe('attachmentService', () => {
  beforeEach(resetMockApi);

  it('上传图片使用 multipart 并归一化时间', async () => {
    setMockResponse('postForm', '/api/attachments', {
      id: 7, name: 'a.png', type: 'image/png', size: 3, created_at: '2026-07-10T00:00:00Z',
    });
    const file = new File(['abc'], 'a.png', { type: 'image/png' });
    const result = await addAttachment(file);
    expect(result.created_at).toBeInstanceOf(Date);
    expect(getMockCalls('postForm', '/api/attachments')[0].body).toBeInstanceOf(FormData);
  });

  it('批量加载附件元数据并保持后端顺序', async () => {
    setMockResponse('post', '/api/attachments/batch', [
      { id: 2, name: 'b.png', type: 'image/png', size: 2, created_at: '2026-07-10T00:00:00Z' },
      { id: 1, name: 'a.png', type: 'image/png', size: 1, created_at: '2026-07-10T00:00:00Z' },
    ]);
    const result = await getAttachments(['2', 'bad', '1']);
    expect(result.map((item) => item.id)).toEqual([2, 1]);
    expect(getMockCalls('post', '/api/attachments/batch')[0].body).toEqual({ ids: [2, 1] });
  });

  it('生成统一后端内容 URL 并删除附件', async () => {
    setMockResponse('delete', '/api/attachments/3', { ok: true });
    expect(getAttachmentContentUrl(3)).toBe('http://localhost:8000/api/attachments/3/content');
    await deleteAttachment(3);
    expect(getMockCalls('delete', '/api/attachments/3')).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Run frontend tests and verify RED**

Run:

```powershell
npm test -- --run tests/services/attachmentService.test.ts
```

Expected: failure because `postForm` and `getApiUrl` do not exist and the service still imports Dexie.

- [ ] **Step 3: Extend the API client minimally**

In `src/services/apiClient.ts`:

```typescript
export function getApiUrl(path: string): string {
  return `${getBackendUrl()}${path}`;
}
```

Change the internal request options body to `unknown | FormData`; when it is `FormData`, assign it directly and do not set `Content-Type` so the browser adds the multipart boundary. Expose:

```typescript
postForm: <T>(path: string, body: FormData) =>
  request<T>(path, { method: 'POST', body }),
```

Extend `tests/mockApiClient.ts` with `postForm`, `getApiUrl`, and the same call recording behavior:

```typescript
postForm: (path: string, body: FormData) => execute('postForm', path, body),
getApiUrl: (path: string) => `http://localhost:8000${path}`,
```

- [ ] **Step 4: Rewrite the attachment adapter and component**

Use this service boundary in `src/services/attachmentService.ts`:

```typescript
import type { Attachment } from '@/types';
import { apiClient, getApiUrl } from './apiClient';

export const MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024;
export const ACCEPTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];

function normalizeAttachment(item: Omit<Attachment, 'created_at'> & { created_at: string | Date }): Attachment {
  return { ...item, created_at: new Date(item.created_at) };
}

export async function addAttachment(file: File): Promise<Attachment> {
  if (file.size > MAX_ATTACHMENT_SIZE) throw new Error('附件大小不能超过 5MB');
  if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) throw new Error('仅支持 JPG/PNG/WebP/GIF 图片格式');
  const form = new FormData();
  form.append('file', file);
  return normalizeAttachment(await apiClient.postForm('/api/attachments', form));
}

export async function getAttachments(ids: string[]): Promise<Attachment[]> {
  const numericIds = ids.map(Number).filter(Number.isInteger);
  if (!numericIds.length) return [];
  const items = await apiClient.post<Array<Omit<Attachment, 'created_at'> & { created_at: string }>>(
    '/api/attachments/batch', { ids: numericIds },
  );
  return items.map(normalizeAttachment);
}

export function getAttachmentContentUrl(id: number): string {
  return getApiUrl(`/api/attachments/${id}/content`);
}

export async function deleteAttachment(id: number): Promise<void> {
  await apiClient.delete(`/api/attachments/${id}`);
}
```

Remove the unused batch-add, batch-delete, object URL, and storage stats exports after confirming they have no callers.

Change `Attachment` in `src/types/index.ts` to contain required `id: number` and remove `blob: Blob`.

In `AttachmentUpload.tsx`, remove object URL creation/revocation and use:

```typescript
const contentUrl = (id: number) => getAttachmentContentUrl(id);
```

Both thumbnail `src` and preview source must use that URL.

- [ ] **Step 5: Run focused tests and type checking**

Run:

```powershell
npm test -- --run tests/services/attachmentService.test.ts
npm run check
```

Expected: service tests pass and TypeScript reports no Blob/Dexie callers.

- [ ] **Step 6: Commit**

```powershell
git add -- src/services/apiClient.ts src/services/attachmentService.ts src/components/AttachmentUpload.tsx src/types/index.ts tests/mockApiClient.ts tests/services/attachmentService.test.ts
git commit -m "refactor: route attachments through backend API"
```

### Task 3: Split backup encryption from obsolete field encryption

**Files:**
- Create: `tests/utils/backupCrypto.test.ts`
- Create: `src/utils/backupCrypto.ts`
- Modify: `src/utils/export.ts`
- Modify: `src/pages/Settings.tsx`
- Delete: `src/utils/crypto.ts`

- [ ] **Step 1: Write failing backup encryption tests**

Create `tests/utils/backupCrypto.test.ts`:

```typescript
import { describe, expect, it } from 'vitest';
import { decryptWithPassword, encryptWithPassword, isEncryptedBackup } from '@/utils/backupCrypto';

describe('backupCrypto', () => {
  it('使用随机 salt/iv 加密并可正确解密', async () => {
    const first = await encryptWithPassword('{"version":1}', 'correct-password');
    const second = await encryptWithPassword('{"version":1}', 'correct-password');
    expect(first).not.toBe(second);
    expect(isEncryptedBackup(first)).toBe(true);
    await expect(decryptWithPassword(first, 'correct-password')).resolves.toBe('{"version":1}');
  });

  it('拒绝空密码、错误密码和损坏格式', async () => {
    await expect(encryptWithPassword('data', '')).rejects.toThrow('备份密码不能为空');
    const encrypted = await encryptWithPassword('data', 'correct');
    await expect(decryptWithPassword(encrypted, 'wrong')).rejects.toThrow('备份密码错误或文件已损坏');
    await expect(decryptWithPassword('backup:v1:broken', 'correct')).rejects.toThrow('加密备份格式损坏');
  });
});
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
npm test -- --run tests/utils/backupCrypto.test.ts
```

Expected: module resolution failure because `backupCrypto.ts` does not exist.

- [ ] **Step 3: Create the focused backup utility**

Move only `bufToBase64`, `base64ToBuf`, `BACKUP_PREFIX`, `PBKDF2_ITERATIONS`, `deriveKeyFromPassword`, `encryptWithPassword`, `decryptWithPassword`, and `isEncryptedBackup` from `crypto.ts` into `backupCrypto.ts`. Do not copy `ENC_PREFIX`, key-store IndexedDB code, or field encryption helpers.

Update imports in `export.ts` and `Settings.tsx`; remove the unused `isEncrypted` import from `export.ts`. Delete `crypto.ts` after `rg` confirms no callers.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```powershell
npm test -- --run tests/utils/backupCrypto.test.ts tests/utils/backendDataBoundary.test.ts
npm run check
```

Expected: both test files pass and type checking succeeds.

- [ ] **Step 5: Commit**

```powershell
git add -- src/utils/backupCrypto.ts src/utils/export.ts src/pages/Settings.tsx tests/utils/backupCrypto.test.ts
git rm -- src/utils/crypto.ts
git commit -m "refactor: isolate password-based backup encryption"
```

### Task 4: Remove Dexie and enforce the final data boundary

**Files:**
- Modify: `tests/utils/backendDataBoundary.test.ts`
- Modify: `tests/setup.ts`
- Modify: `package.json`
- Modify: `package-lock.json`
- Delete: `src/db/index.ts`
- Delete: `tests/helpers.ts`

- [ ] **Step 1: Write the failing architecture test**

Extend `backendDataBoundary.test.ts`:

```typescript
it('前端生产代码和依赖不再包含业务 IndexedDB', () => {
  const packageJson = readFileSync(resolve('package.json'), 'utf8');
  const attachmentService = readFileSync(resolve('src/services/attachmentService.ts'), 'utf8');
  const setup = readFileSync(resolve('tests/setup.ts'), 'utf8');

  expect(packageJson).not.toContain('"dexie"');
  expect(packageJson).not.toContain('"fake-indexeddb"');
  expect(attachmentService).not.toContain("from '@/db'");
  expect(setup).not.toContain('fake-indexeddb');
});
```

- [ ] **Step 2: Run the boundary test and verify RED**

Run:

```powershell
npm test -- --run tests/utils/backendDataBoundary.test.ts
```

Expected: failure because package dependencies and test setup still contain IndexedDB packages.

- [ ] **Step 3: Remove dead files and dependencies**

Delete `src/db/index.ts` and unused `tests/helpers.ts`. Remove the first five fake-indexeddb lines from `tests/setup.ts`, retaining matchMedia and ResizeObserver setup.

Run:

```powershell
npm uninstall dexie fake-indexeddb
```

This must update both `package.json` and `package-lock.json`; do not hand-edit the lock file.

- [ ] **Step 4: Verify the boundary is GREEN**

Run:

```powershell
rg -n "@/db|Dexie|fake-indexeddb|indexedDB|encryptField|decryptField|XianyuKeyStore" src tests package.json
npm test -- --run tests/utils/backendDataBoundary.test.ts
npm run check
```

Expected: `rg` finds only assertion strings in the boundary test, the boundary tests pass, and type checking succeeds.

- [ ] **Step 5: Commit**

```powershell
git add -- package.json package-lock.json tests/setup.ts tests/utils/backendDataBoundary.test.ts
git rm -- src/db/index.ts tests/helpers.ts
git commit -m "refactor: remove frontend IndexedDB dependency"
```

### Task 5: Full verification and runtime smoke test

**Files:**
- Modify only if verification exposes a defect directly caused by Tasks 1-4.

- [ ] **Step 1: Run static and automated verification**

```powershell
npm test -- --run
npm run check
npm run build
python -m pytest server/backend -q
git diff --check
```

Expected: all tests pass, production build succeeds with only the known Vite `use client` and chunk-size warnings, and no whitespace errors exist.

- [ ] **Step 2: Rebuild runtime containers**

```powershell
docker compose up -d --build backend web
docker ps --filter name=xianyugou
```

Expected: backend, web, and mail containers are Up.

- [ ] **Step 3: Run a real attachment smoke test without retaining test data**

Run this PowerShell script. It creates a fixed 1×1 PNG in the OS temp directory, verifies the downloaded bytes, deletes the created row in `finally`, and removes the local fixture:

```powershell
$fixture = Join-Path $env:TEMP 'xianyugou-attachment-smoke.png'
$download = Join-Path $env:TEMP 'xianyugou-attachment-smoke-download.png'
$png = [Convert]::FromBase64String('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
[IO.File]::WriteAllBytes($fixture, $png)
$created = $null
try {
  $created = Invoke-RestMethod -Method Post -Uri 'http://localhost:18001/api/attachments' -Form @{ file = Get-Item $fixture }
  Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:18001/api/attachments/$($created.id)/content" -OutFile $download
  if ([Convert]::ToHexString([IO.File]::ReadAllBytes($fixture)) -ne [Convert]::ToHexString([IO.File]::ReadAllBytes($download))) { throw 'attachment bytes mismatch' }
} finally {
  if ($created) { Invoke-RestMethod -Method Delete -Uri "http://localhost:18001/api/attachments/$($created.id)" | Out-Null }
  Remove-Item -LiteralPath $fixture, $download -Force -ErrorAction SilentlyContinue
}
```

Expected: no error, matching bytes, and the test attachment is deleted even when verification fails.

- [ ] **Step 4: Recheck schema and rollback assets**

```powershell
docker exec xianyugou-backend python -m app.maintenance.database_schema current
docker exec xianyugou-backend python -m app.maintenance.database_backup verify --database /app/backups/xianyu-20260710-pre-alembic.db --manifest /app/backups/xianyu-20260710-pre-alembic.manifest.json
```

Expected: current=head=`20260710_02` and backup verification succeeds.

- [ ] **Step 5: Confirm repository state**

```powershell
git status --short
git log -6 --oneline
```

Expected: clean worktree and the four Stage 2B implementation commits after the design/plan commits.

- [ ] **Step 6: Update persistent project memory**

Append a concise Stage 2B entry to `E:\Obsidian\Codex\projects\XianyuGou.md` containing decisions, commit IDs, verification counts, remaining risks, and the next architecture stage. Do not record attachment contents, credentials, or full command output.
