"""Compatibility facade for the runtime locking helpers."""

import os

from thg_protocol.runtime.locking import RunLockedError, acquire_run_lock, unlock_run

__all__ = ["RunLockedError", "acquire_run_lock", "unlock_run", "os"]
