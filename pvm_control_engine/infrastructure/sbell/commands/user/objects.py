"""Restricted user/objects query facade; caller never supplies XML or query text."""

from enum import StrEnum

from plaivid_cli.domain.models import canonical_uuid


class ObjectsQuery(StrEnum):
    VM_INVENTORY = "vm_inventory"
    VM_DETAIL = "vm_detail"
    VM_TAP_MAPPING = "vm_tap_mapping"
    DESKTOP_LIST = "desktop_list"
    DASHBOARD = "dashboard"


class UserObjects:
    def __init__(self, application):
        self.application = application

    def execute(self, token: str, query: ObjectsQuery | str, *, uuid: str | None = None):
        try:
            query = ObjectsQuery(query)
        except ValueError as exc:
            raise ValueError("unsupported objects query") from exc
        if query is ObjectsQuery.VM_INVENTORY:
            if uuid is not None:
                raise ValueError("inventory query takes no UUID")
            return self.application.inventory(token)[1]
        if query is ObjectsQuery.VM_DETAIL:
            if uuid is None:
                raise ValueError("detail query requires a UUID")
            key = canonical_uuid(uuid)
            if key != uuid:
                raise ValueError("UUID must be canonical")
            return self.application.detail(token, key)
        if uuid is not None:
            raise ValueError("query takes no UUID")
        section = {
            ObjectsQuery.VM_TAP_MAPPING: "tap_mapping",
            ObjectsQuery.DESKTOP_LIST: "desktops",
            ObjectsQuery.DASHBOARD: "dashboard",
        }.get(query)
        if section is not None:
            return self.application.refresh(token, sections=(section,)).section(section)
        raise ValueError("unsupported objects query")
