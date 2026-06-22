"""Automation domain package: the trigger/action wire vocabulary and the `drive` engine.

`model.py` owns the closed `Trigger` (`Watch | Schedule | Manual`) and `Action`
(`AgentAction | Notify | Embed | Sync`) tagged unions, the `AgentSkill` in-arm discriminant, the
`AutomationSpec` wire record, the `AutomationReceipt` typed receipt, and the closed `AutomationFault`
rail. `engine.py` owns the single polymorphic `drive(spec, cfg) -> Envelope` entrypoint, the
`_decode_spec` admission converter, and the anyio lane coordination. This package adds no re-export
surface: `admin.rails` is the one CLI mount barrel and carries the public `drive` re-export alongside
the other rail callables, while `admin.__main__` binds the `AutomationSpec` decoder and `_decode_spec`
converter straight off `model.py`/`engine.py`. Re-forwarding that vocabulary here would mint a second
canonical name per type, so consumers reach the `model`/`engine` owners directly. The
`AutomationConfig` group those specs validate against is owned by `admin.settings` and reached through
`settings()`.
"""
