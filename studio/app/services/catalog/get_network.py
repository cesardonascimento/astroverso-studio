from app.services.catalog.entries import Network
from app.services.catalog.list_networks import ListNetworks


class GetNetwork:
    def execute(self, network_id: str) -> Network:
        network = next((item for item in ListNetworks().execute() if item.id == network_id), None)
        if network is None:
            raise LookupError(f"rede desconhecida: {network_id}")
        return network
