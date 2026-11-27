"""The fixed PVM VM-stop command."""

import xml.etree.ElementTree as ET

from pvm_control_engine.domain.models import Action
from pvm_control_engine.infrastructure.sbell.commands.vm.base import VMActionCommand


class StopVM(VMActionCommand):
    ACTION = Action.STOP
    COMMAND = "stop"

    def build_params(self, vm_uuid: str) -> str:
        root = ET.Element("vm_key")
        root.text = vm_uuid
        return ET.tostring(root, encoding="unicode", short_empty_elements=False)
