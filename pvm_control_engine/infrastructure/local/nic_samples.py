"""Local read-only physical NIC counter query facade."""

class LocalNicSamples:
    def __init__(self, application):
        self.application = application

    def execute(self, token: str):
        snapshot = self.application.refresh(token, sections=("physical_nics", "nic_samples"))
        return snapshot.section("physical_nics"), snapshot.section("nic_samples")
