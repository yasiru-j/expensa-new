"""/api/account — account-settings endpoints.

DELETE hard-deletes the caller's account: every expense, line item, and
usage row (via ON DELETE CASCADE from users), plus every stored file in
object storage. Irreversible; the frontend requires an explicit typed
confirmation before ever calling this.

Follows the same pattern as DELETE /api/expenses/{id}: file keys are
collected inside the request's own RLS-scoped transaction, the user row is
deleted (cascading everything else) in that same transaction, and the actual
S3 deletes are deferred to background tasks that only run after the
transaction has committed — so a later failure in this request can't leave
files deleted with the row rolled back, or vice versa.

PATCH updates account-profile fields (currently just full_name). It always
operates on `current_user` from the JWT — never a client-supplied id — since
the `users` table itself carries no RLS policy (see migration 0001); scoping
a write to the caller's own row is this endpoint's job, not the database's.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import clear_refresh_cookie
from app.core.deps import get_current_user, get_db
from app.db.models.expense import Expense
from app.db.models.user import User
from app.schemas.user import AccountUpdate, UserRead
from app.storage.s3 import delete_object

router = APIRouter(prefix="/api/account", tags=["account"])


@router.patch("", response_model=UserRead)
async def update_account(
    body: AccountUpdate,
    current_user: User = Depends(get_current_user),
) -> User:
    if "full_name" in body.model_fields_set:
        current_user.full_name = body.full_name
    return current_user


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    response: Response,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    # RLS scopes this to the caller's own rows, same as every other query in
    # this app — no explicit WHERE user_id filter.
    file_keys = (
        (await db.execute(select(Expense.file_url).where(Expense.file_url.is_not(None))))
        .scalars()
        .all()
    )

    # Deleting the user cascades to expenses -> line_items and to usage
    # (all ON DELETE CASCADE, see migration 0001) — one statement removes
    # every trace of this account from the database.
    await db.delete(current_user)

    for key in file_keys:
        background_tasks.add_task(delete_object, key)

    clear_refresh_cookie(response)
