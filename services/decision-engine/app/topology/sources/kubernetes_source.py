# app/topology/kubernetes_source.py
from kubernetes import client, config, watch
from app.core.models import ServiceNode, DependencyEdge

class KubernetesTopologySource:
    def __init__(self):
        try:
            config.load_incluster_config()      # Component 2 6.1
        except config.ConfigException:
            config.load_kube_config()

    async def watch_services(self, on_node, on_edge, on_delete):
        v1 = client.CoreV1Api()
        w = watch.Watch()
        for event in w.stream(v1.list_service_for_all_namespaces, timeout_seconds=0):
            obj = event["object"]
            if obj.metadata.namespace not in ("default", "self-healing", "services"):
                continue
            if event["type"] == "DELETED":
                on_delete(obj.metadata.name)
            else:
                on_node(ServiceNode(
                    id=obj.metadata.name,
                    name=obj.metadata.name,
                    namespace=obj.metadata.namespace,
                ))