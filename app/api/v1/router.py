"""v1 路由聚合。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import audio, auth, chat, children, followup, game, knowledge, safety, training

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(children.router)
api_router.include_router(audio.router)
api_router.include_router(chat.router)
api_router.include_router(training.router)
api_router.include_router(game.router)
api_router.include_router(followup.router)
api_router.include_router(knowledge.router)
api_router.include_router(safety.router)

__all__ = ["api_router"]
