"""The fixed PVM VM-start command and its exact XML contract."""

import xml.etree.ElementTree as ET

from pvm_control_engine.domain.models import Action
from pvm_control_engine.infrastructure.sbell.commands.vm.base import VMActionCommand


class StartVM(VMActionCommand):
    ACTION = Action.START
    COMMAND = "start"

    def build_params(self, vm_uuid: str) -> str:
        root = ET.Element("vm_start")
        ET.SubElement(root, "vm_key").text = vm_uuid
        ET.SubElement(root, "host").text = "auto"
        version = ET.SubElement(root, "version_start")
        ET.SubElement(version, "version_enable").text = "no"
        ET.SubElement(version, "version_vkey").text = ""
        ET.SubElement(root, "exit_from_replicate").text = "yes"
        return ET.tostring(root, encoding="unicode", short_empty_elements=False)
