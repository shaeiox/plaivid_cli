"""The fixed PVM VM-kill command."""

import xml.etree.ElementTree as ET

from pvm_control_engine.domain.models import Action
from pvm_control_engine.infrastructure.sbell.commands.vm.base import VMActionCommand


class KillVM(VMActionCommand):
    ACTION = Action.KILL
    COMMAND = "kill"

    def build_params(self, vm_uuid: str) -> str:
        root = ET.Element("vm_key")
        root.text = vm_uuid
        return ET.tostring(root, encoding="unicode", short_empty_elements=False)
