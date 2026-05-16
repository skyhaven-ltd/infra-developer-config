from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


AREA_HEADER_RE = re.compile(r"^#{41} [A-Z0-9][A-Z0-9 /&()_.-]* #{41}$")
ASSIGNMENT_RE = re.compile(r"(?m)^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*=")
TOP_LEVEL_BLOCK_RE = re.compile(
    r'(?m)^(?P<indent>[ \t]*)(?P<kind>terraform|provider|variable|output|locals|data|resource|module)\b(?P<labels>[^{\n]*)\{'
)
SECRET_NAME_RE = re.compile(
    r"(password|passwd|pwd|secret|client_secret|token|api[_-]?key|access[_-]?key|private[_-]?key|connection[_-]?string)",
    re.IGNORECASE,
)

# Microsoft Cloud Adoption Framework resource abbreviation recommendations.
# Source: https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/resource-abbreviations
# Last checked: 2026-05-16. Some Azure resource provider namespaces collapse into
# one Terraform resource type and are therefore represented as multiple accepted
# abbreviations for that type.
CAF_ABBREVIATIONS_BY_PROVIDER_NAMESPACE: dict[str, tuple[str, ...]] = {
    "Microsoft.AlertsManagement/actionRules": ("apr",),
    "Microsoft.AnalysisServices/servers": ("as",),
    "Microsoft.ApiManagement/service": ("apim",),
    "Microsoft.App/containerApps": ("ca",),
    "Microsoft.App/jobs": ("caj",),
    "Microsoft.App/managedEnvironments": ("cae",),
    "Microsoft.AppConfiguration/configurationStores": ("appcs",),
    "Microsoft.Authorization/policyDefinitions": (),
    "Microsoft.Automation/automationAccounts": ("aa",),
    "Microsoft.Batch/batchAccounts": ("ba",),
    "Microsoft.BotService/botServices": ("bot",),
    "Microsoft.Cache/RedisEnterprise": ("amr",),
    "Microsoft.Cdn/profiles": ("cdnp", "afd"),
    "Microsoft.Cdn/profiles/afdEndpoints": ("fde",),
    "Microsoft.Cdn/profiles/endpoints": ("cdne",),
    "Microsoft.CognitiveServices/accounts": (
        "ais",
        "aif",
        "oai",
        "cv",
        "cm",
        "cs",
        "cstv",
        "cstvt",
        "di",
        "face",
        "hi",
        "ir",
        "lang",
        "spch",
        "trsl",
    ),
    "Microsoft.CognitiveServices/accounts/projects": ("proj",),
    "Microsoft.Communication/communicationServices": ("acs",),
    "Microsoft.Compute/availabilitySets": ("avail",),
    "Microsoft.Compute/cloudServices": ("cld",),
    "Microsoft.Compute/diskEncryptionSets": ("des",),
    "Microsoft.Compute/disks": ("osdisk", "disk"),
    "Microsoft.Compute/galleries": ("gal",),
    "Microsoft.Compute/proximityPlacementGroups": ("ppg",),
    "Microsoft.Compute/restorePointCollections": ("rpc",),
    "Microsoft.Compute/snapshots": ("snap",),
    "Microsoft.Compute/sshPublicKeys": ("sshkey",),
    "Microsoft.Compute/virtualMachineScaleSets": ("vmss",),
    "Microsoft.Compute/virtualMachines": ("vm",),
    "Microsoft.ContainerInstance/containerGroups": ("ci",),
    "Microsoft.ContainerRegistry/registries": ("cr",),
    "Microsoft.ContainerService/managedClusters": ("aks",),
    "Microsoft.ContainerService/managedClusters/agentPools": ("npsystem", "np"),
    "Microsoft.DBforMySQL/servers": ("mysql",),
    "Microsoft.DBforPostgreSQL/serverGroupsv2": ("cospos",),
    "Microsoft.DBforPostgreSQL/servers": ("psql",),
    "Microsoft.Dashboard/grafana": ("amg",),
    "Microsoft.DataFactory/factories": ("adf",),
    "Microsoft.DataLakeStore/accounts": ("dls",),
    "Microsoft.DataMigration/services": ("dms",),
    "Microsoft.DataProtection/backupVaults": ("bvault",),
    "Microsoft.DataProtection/backupVaults/backupPolicies": ("bkpol",),
    "Microsoft.DataProtection/resourceGuards": ("rgd",),
    "Microsoft.Databricks/workspaces": ("dbw",),
    "Microsoft.Databricks/workspaces/accessConnectors": ("dbac",),
    "Microsoft.DesktopVirtualization/applicationGroups": ("vdag",),
    "Microsoft.DesktopVirtualization/hostPools": ("vdpool",),
    "Microsoft.DesktopVirtualization/scalingPlans": ("vdscaling",),
    "Microsoft.DesktopVirtualization/workspaces": ("vdws",),
    "Microsoft.DevOpsInfrastructure/pools": ("mdp",),
    "Microsoft.Devices/IotHubs": ("iot",),
    "Microsoft.Devices/provisioningServices": ("provs",),
    "Microsoft.Devices/provisioningServices/certificates": ("pcert",),
    "Microsoft.DigitalTwins/digitalTwinsInstances": ("dt",),
    "Microsoft.DocumentDB/databaseAccounts": ("coscas", "cosmon"),
    "Microsoft.DocumentDB/databaseAccounts/sqlDatabases": ("cosmos",),
    "Microsoft.DocumentDb/databaseAccounts": ("cosno", "costab", "cosgrm"),
    "Microsoft.EventGrid/domains": ("evgd",),
    "Microsoft.EventGrid/domains/topics": ("evgt",),
    "Microsoft.EventGrid/eventSubscriptions": ("evgs",),
    "Microsoft.EventGrid/namespaces": ("evgns",),
    "Microsoft.EventGrid/systemTopics": ("egst",),
    "Microsoft.EventHub/namespaces": ("evhns",),
    "Microsoft.EventHub/namespaces/eventHubs": ("evh",),
    "Microsoft.Fabric/capacities": ("fc",),
    "Microsoft.HDInsight/clusters": ("hadoop", "hbase", "kafka", "spark", "storm", "mls"),
    "Microsoft.HybridCompute/gateways": ("arcgw",),
    "Microsoft.HybridCompute/machines": ("arcs",),
    "Microsoft.HybridCompute/privateLinkScopes": ("pls",),
    "Microsoft.Insights/actionGroups": ("ag",),
    "Microsoft.Insights/components": ("appi",),
    "Microsoft.Insights/dataCollectionEndpoints": ("dce",),
    "Microsoft.Insights/dataCollectionRules": ("dcr",),
    "Microsoft.KeyVault/managedHSMs": ("kvmhsm",),
    "Microsoft.KeyVault/vaults": ("kv",),
    "Microsoft.Kubernetes/connectedClusters": ("arck",),
    "Microsoft.Kusto/clusters": ("dec",),
    "Microsoft.Kusto/clusters/databases": ("dedb",),
    "Microsoft.LoadTestService/loadTests": ("lt",),
    "Microsoft.Logic/integrationAccounts": ("ia",),
    "Microsoft.Logic/workflows": ("logic",),
    "Microsoft.MachineLearningServices/workspaces": ("hub", "proj", "mlw"),
    "Microsoft.Maintenance/maintenanceConfigurations": ("mc",),
    "Microsoft.ManagedIdentity/userAssignedIdentities": ("id",),
    "Microsoft.Management/managementGroups": ("mg",),
    "Microsoft.Maps/accounts": ("map",),
    "Microsoft.Migrate/assessmentProjects": ("migr",),
    "Microsoft.Network/applicationGateways": ("agw",),
    "Microsoft.Network/applicationSecurityGroups": ("asg",),
    "Microsoft.Network/azureFirewalls": ("afw",),
    "Microsoft.Network/bastionHosts": ("bas",),
    "Microsoft.Network/connections": ("con",),
    "Microsoft.Network/dnsForwardingRulesets": ("dnsfrs",),
    "Microsoft.Network/dnsResolvers": ("dnspr",),
    "Microsoft.Network/dnsResolvers/inboundEndpoints": ("in",),
    "Microsoft.Network/dnsResolvers/outboundEndpoints": ("out",),
    "Microsoft.Network/dnsZones": (),
    "Microsoft.Network/expressRouteCircuits": ("erc",),
    "Microsoft.Network/expressRoutePorts": ("erd",),
    "Microsoft.Network/firewallPolicies": ("afwp", "waf"),
    "Microsoft.Network/firewallPolicies/ruleGroups": ("wafrg",),
    "Microsoft.Network/frontDoors": ("afd",),
    "Microsoft.Network/frontdoorWebApplicationFirewallPolicies": ("fdfp",),
    "Microsoft.Network/ipGroups": ("ipg",),
    "Microsoft.Network/loadBalancers": ("lbi", "lbe"),
    "Microsoft.Network/loadBalancers/inboundNatRules": ("rule",),
    "Microsoft.Network/localNetworkGateways": ("lgw",),
    "Microsoft.Network/natGateways": ("ng",),
    "Microsoft.Network/networkInterfaces": ("nic",),
    "Microsoft.Network/networkManagers": ("vnm",),
    "Microsoft.Network/networkSecurityGroups": ("nsg",),
    "Microsoft.Network/networkSecurityGroups/securityRules": ("nsgsr",),
    "Microsoft.Network/networkSecurityPerimeters": ("nsp",),
    "Microsoft.Network/networkWatchers": ("nw",),
    "Microsoft.Network/privateDnsZones": (),
    "Microsoft.Network/privateEndpoints": ("pep",),
    "Microsoft.Network/privateLinkServices": ("pl",),
    "Microsoft.Network/publicIPAddresses": ("pip",),
    "Microsoft.Network/publicIPPrefixes": ("ippre",),
    "Microsoft.Network/routeFilters": ("rf",),
    "Microsoft.Network/routeTables": ("rt",),
    "Microsoft.Network/routeTables/routes": ("udr",),
    "Microsoft.Network/serviceEndPointPolicies": ("se",),
    "Microsoft.Network/trafficManagerProfiles": ("traf",),
    "Microsoft.Network/virtualHubs": ("rtserv", "vhub"),
    "Microsoft.Network/virtualNetworkGateways": ("ergw", "vgw"),
    "Microsoft.Network/virtualNetworks": ("vnet",),
    "Microsoft.Network/virtualNetworks/subnets": ("snet",),
    "Microsoft.Network/virtualNetworks/virtualNetworkPeerings": ("peer",),
    "Microsoft.Network/virtualWans": ("vwan",),
    "Microsoft.Network/vpnGateways": ("vpng",),
    "Microsoft.Network/vpnGateways/vpnConnections": ("vcn",),
    "Microsoft.Network/vpnGateways/vpnSites": ("vst",),
    "Microsoft.NotificationHubs/namespaces": ("ntfns",),
    "Microsoft.NotificationHubs/namespaces/notificationHubs": ("ntf",),
    "Microsoft.OperationalInsights/querypacks": ("pack",),
    "Microsoft.OperationalInsights/workspaces": ("log",),
    "Microsoft.PowerBIDedicated/capacities": ("pbi",),
    "Microsoft.Purview/accounts": ("pview",),
    "Microsoft.RecoveryServices/vaults": ("rsv",),
    "Microsoft.Resources/deploymentScripts": ("script",),
    "Microsoft.Resources/resourceGroups": ("rg",),
    "Microsoft.Resources/templateSpecs": ("ts",),
    "Microsoft.Search/searchServices": ("srch",),
    "Microsoft.ServiceBus/namespaces": ("sbns",),
    "Microsoft.ServiceBus/namespaces/queues": ("sbq",),
    "Microsoft.ServiceBus/namespaces/topics": ("sbt",),
    "Microsoft.ServiceBus/namespaces/topics/subscriptions": ("sbts",),
    "Microsoft.ServiceFabric/clusters": ("sf",),
    "Microsoft.ServiceFabric/managedClusters": ("sfmc",),
    "Microsoft.SignalRService/SignalR": ("sigr",),
    "Microsoft.SignalRService/webPubSub": ("wps",),
    "Microsoft.Sql/managedInstances": ("sqlmi",),
    "Microsoft.Sql/servers": ("sql",),
    "Microsoft.Sql/servers/databases": ("sqldb",),
    "Microsoft.Sql/servers/elasticpool": ("sqlep",),
    "Microsoft.Sql/servers/jobAgents": ("sqlja",),
    "Microsoft.Storage/storageAccounts": ("st", "stvm"),
    "Microsoft.Storage/storageAccounts/fileServices/shares": ("share",),
    "Microsoft.StorageSync/storageSyncServices": ("sss",),
    "Microsoft.StreamAnalytics/cluster": ("asa",),
    "Microsoft.Synapse/privateLinkHubs": ("synplh",),
    "Microsoft.Synapse/workspaces": ("synw",),
    "Microsoft.Synapse/workspaces/bigDataPools": ("synsp",),
    "Microsoft.Synapse/workspaces/sqlPools": ("syndp",),
    "Microsoft.TimeSeriesInsights/environments": ("tsi",),
    "Microsoft.VideoIndexer/accounts": ("avi",),
    "Microsoft.VirtualMachineImages/imageTemplates": ("it",),
    "Microsoft.Web/hostingEnvironments": ("ase", "host"),
    "Microsoft.Web/serverFarms": ("asp",),
    "Microsoft.Web/sites": ("func", "app"),
    "Microsoft.Web/staticSites": ("stapp",),
}

CAF_PREFIXES: dict[str, tuple[str, ...]] = {
    "azurerm_ai_foundry": ("aif",),
    "azurerm_ai_foundry_project": ("proj",),
    "azurerm_analysis_services_server": ("as",),
    "azurerm_api_management": ("apim",),
    "azurerm_app_configuration": ("appcs",),
    "azurerm_app_service": ("app",),
    "azurerm_app_service_environment": ("ase", "host"),
    "azurerm_app_service_environment_v3": ("ase", "host"),
    "azurerm_app_service_plan": ("asp",),
    "azurerm_application_gateway": ("agw",),
    "azurerm_application_insights": ("appi",),
    "azurerm_application_security_group": ("asg",),
    "azurerm_automation_account": ("aa",),
    "azurerm_availability_set": ("avail",),
    "azurerm_bastion_host": ("bas",),
    "azurerm_batch_account": ("ba",),
    "azurerm_bot_service_azure_bot": ("bot",),
    "azurerm_cdn_endpoint": ("cdne",),
    "azurerm_cdn_frontdoor_endpoint": ("fde",),
    "azurerm_cdn_frontdoor_firewall_policy": ("fdfp",),
    "azurerm_cdn_frontdoor_profile": ("afd",),
    "azurerm_cdn_profile": ("cdnp",),
    "azurerm_cognitive_account": (
        "ais",
        "aif",
        "oai",
        "cv",
        "cm",
        "cs",
        "cstv",
        "cstvt",
        "di",
        "face",
        "hi",
        "ir",
        "lang",
        "spch",
        "trsl",
    ),
    "azurerm_communication_service": ("acs",),
    "azurerm_container_app": ("ca",),
    "azurerm_container_app_environment": ("cae",),
    "azurerm_container_app_job": ("caj",),
    "azurerm_container_group": ("ci",),
    "azurerm_container_registry": ("cr",),
    "azurerm_cosmosdb_account": ("coscas", "cosmon", "cosno", "costab", "cosgrm", "cosmos"),
    "azurerm_cosmosdb_cassandra_keyspace": ("coscas",),
    "azurerm_cosmosdb_gremlin_database": ("cosgrm",),
    "azurerm_cosmosdb_mongo_database": ("cosmon",),
    "azurerm_cosmosdb_sql_database": ("cosmos", "cosno"),
    "azurerm_cosmosdb_table": ("costab",),
    "azurerm_dashboard_grafana": ("amg",),
    "azurerm_data_factory": ("adf",),
    "azurerm_data_lake_store": ("dls",),
    "azurerm_data_protection_backup_policy_blob_storage": ("bkpol",),
    "azurerm_data_protection_backup_vault": ("bvault",),
    "azurerm_databricks_access_connector": ("dbac",),
    "azurerm_databricks_workspace": ("dbw",),
    "azurerm_dedicated_host": ("host",),
    "azurerm_dev_center": ("mdp",),
    "azurerm_dev_test_lab": ("lt",),
    "azurerm_digital_twins_instance": ("dt",),
    "azurerm_disk_encryption_set": ("des",),
    "azurerm_dns_zone": (),
    "azurerm_eventgrid_domain": ("evgd",),
    "azurerm_eventgrid_domain_topic": ("evgt",),
    "azurerm_eventgrid_event_subscription": ("evgs",),
    "azurerm_eventgrid_namespace": ("evgns",),
    "azurerm_eventgrid_system_topic": ("egst",),
    "azurerm_eventhub": ("evh",),
    "azurerm_eventhub_namespace": ("evhns",),
    "azurerm_express_route_circuit": ("erc",),
    "azurerm_express_route_port": ("erd",),
    "azurerm_fabric_capacity": ("fc",),
    "azurerm_firewall": ("afw",),
    "azurerm_firewall_policy": ("afwp", "waf"),
    "azurerm_function_app": ("func",),
    "azurerm_hdinsight_hadoop_cluster": ("hadoop",),
    "azurerm_hdinsight_hbase_cluster": ("hbase",),
    "azurerm_hdinsight_interactive_query_cluster": ("hadoop",),
    "azurerm_hdinsight_kafka_cluster": ("kafka",),
    "azurerm_hdinsight_ml_services_cluster": ("mls",),
    "azurerm_hdinsight_spark_cluster": ("spark",),
    "azurerm_hdinsight_storm_cluster": ("storm",),
    "azurerm_image_template": ("it",),
    "azurerm_iothub": ("iot",),
    "azurerm_iothub_dps": ("provs",),
    "azurerm_iothub_dps_certificate": ("pcert",),
    "azurerm_ip_group": ("ipg",),
    "azurerm_key_vault": ("kv",),
    "azurerm_key_vault_managed_hardware_security_module": ("kvmhsm",),
    "azurerm_kubernetes_cluster": ("aks",),
    "azurerm_kubernetes_cluster_node_pool": ("npsystem", "np"),
    "azurerm_kusto_cluster": ("dec",),
    "azurerm_kusto_database": ("dedb",),
    "azurerm_linux_function_app": ("func",),
    "azurerm_linux_virtual_machine": ("vm",),
    "azurerm_linux_virtual_machine_scale_set": ("vmss",),
    "azurerm_linux_web_app": ("app",),
    "azurerm_load_balancer": ("lbi", "lbe"),
    "azurerm_lb": ("lbi", "lbe"),
    "azurerm_lb_nat_rule": ("rule",),
    "azurerm_local_network_gateway": ("lgw",),
    "azurerm_log_analytics_query_pack": ("pack",),
    "azurerm_log_analytics_workspace": ("log",),
    "azurerm_logic_app_integration_account": ("ia",),
    "azurerm_logic_app_workflow": ("logic",),
    "azurerm_machine_learning_workspace": ("hub", "proj", "mlw"),
    "azurerm_maintenance_configuration": ("mc",),
    "azurerm_management_group": ("mg",),
    "azurerm_managed_disk": ("osdisk", "disk"),
    "azurerm_maps_account": ("map",),
    "azurerm_mariadb_server": ("mysql",),
    "azurerm_mssql_database": ("sqldb",),
    "azurerm_mssql_elasticpool": ("sqlep",),
    "azurerm_mssql_job_agent": ("sqlja",),
    "azurerm_mssql_managed_instance": ("sqlmi",),
    "azurerm_mssql_server": ("sql",),
    "azurerm_mysql_flexible_server": ("mysql",),
    "azurerm_mysql_server": ("mysql",),
    "azurerm_nat_gateway": ("ng",),
    "azurerm_network_connection_monitor": ("con",),
    "azurerm_network_interface": ("nic",),
    "azurerm_network_manager": ("vnm",),
    "azurerm_network_security_group": ("nsg",),
    "azurerm_network_security_rule": ("nsgsr",),
    "azurerm_network_watcher": ("nw",),
    "azurerm_notification_hub": ("ntf",),
    "azurerm_notification_hub_namespace": ("ntfns",),
    "azurerm_orchestrated_virtual_machine_scale_set": ("vmss",),
    "azurerm_postgresql_flexible_server": ("psql",),
    "azurerm_postgresql_server": ("psql",),
    "azurerm_powerbi_embedded": ("pbi",),
    "azurerm_private_dns_resolver": ("dnspr",),
    "azurerm_private_dns_resolver_dns_forwarding_ruleset": ("dnsfrs",),
    "azurerm_private_dns_resolver_inbound_endpoint": ("in",),
    "azurerm_private_dns_resolver_outbound_endpoint": ("out",),
    "azurerm_private_dns_zone": (),
    "azurerm_private_endpoint": ("pep",),
    "azurerm_private_link_service": ("pl",),
    "azurerm_proximity_placement_group": ("ppg",),
    "azurerm_public_ip": ("pip",),
    "azurerm_public_ip_prefix": ("ippre",),
    "azurerm_purview_account": ("pview",),
    "azurerm_recovery_services_vault": ("rsv",),
    "azurerm_redis_enterprise_cluster": ("amr",),
    "azurerm_resource_group": ("rg",),
    "azurerm_resource_group_template_deployment": ("ts",),
    "azurerm_route": ("udr",),
    "azurerm_route_filter": ("rf",),
    "azurerm_route_server": ("rtserv",),
    "azurerm_route_table": ("rt",),
    "azurerm_search_service": ("srch",),
    "azurerm_service_fabric_cluster": ("sf",),
    "azurerm_service_fabric_managed_cluster": ("sfmc",),
    "azurerm_service_plan": ("asp",),
    "azurerm_servicebus_namespace": ("sbns",),
    "azurerm_servicebus_queue": ("sbq",),
    "azurerm_servicebus_subscription": ("sbts",),
    "azurerm_servicebus_topic": ("sbt",),
    "azurerm_signalr_service": ("sigr",),
    "azurerm_snapshot": ("snap",),
    "azurerm_ssh_public_key": ("sshkey",),
    "azurerm_static_site": ("stapp",),
    "azurerm_storage_account": ("st", "stvm"),
    "azurerm_storage_share": ("share",),
    "azurerm_storage_sync": ("sss",),
    "azurerm_stream_analytics_cluster": ("asa",),
    "azurerm_subnet": ("snet",),
    "azurerm_synapse_private_link_hub": ("synplh",),
    "azurerm_synapse_spark_pool": ("synsp",),
    "azurerm_synapse_sql_pool": ("syndp",),
    "azurerm_synapse_workspace": ("synw",),
    "azurerm_template_deployment": ("ts",),
    "azurerm_template_spec": ("ts",),
    "azurerm_traffic_manager_profile": ("traf",),
    "azurerm_user_assigned_identity": ("id",),
    "azurerm_virtual_desktop_application_group": ("vdag",),
    "azurerm_virtual_desktop_host_pool": ("vdpool",),
    "azurerm_virtual_desktop_scaling_plan": ("vdscaling",),
    "azurerm_virtual_desktop_workspace": ("vdws",),
    "azurerm_virtual_hub": ("rtserv", "vhub"),
    "azurerm_virtual_machine": ("vm",),
    "azurerm_virtual_machine_scale_set": ("vmss",),
    "azurerm_virtual_network": ("vnet",),
    "azurerm_virtual_network_gateway": ("ergw", "vgw"),
    "azurerm_virtual_network_peering": ("peer",),
    "azurerm_virtual_wan": ("vwan",),
    "azurerm_windows_function_app": ("func",),
    "azurerm_windows_virtual_machine": ("vm",),
    "azurerm_windows_virtual_machine_scale_set": ("vmss",),
    "azurerm_windows_web_app": ("app",),
}

AZURERM_NOT_TAGGABLE_EXACT = {
    "azurerm_federated_identity_credential",
    "azurerm_monitor_diagnostic_setting",
    "azurerm_private_dns_zone_virtual_network_link",
    "azurerm_role_assignment",
    "azurerm_role_definition",
    "azurerm_subnet",
}
AZURERM_NOT_TAGGABLE_PREFIXES = (
    "azurerm_api_management_api",
    "azurerm_app_service_custom_hostname_binding",
    "azurerm_key_vault_access_policy",
    "azurerm_management_lock",
    "azurerm_private_dns_",
)


class SkillError(RuntimeError):
    pass


@dataclass(frozen=True)
class Block:
    kind: str
    labels: list[str]
    start: int
    end: int
    line: int
    text: str
    file: str


def out(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def fail(message: str) -> int:
    print(json.dumps({"error": message}, indent=2), file=sys.stderr)
    return 1


def target_dir(raw: str) -> Path:
    path = Path(raw).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise SkillError(f"Target directory does not exist: {path}")
    return path


def rel_path(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def line_no(text: str, idx: int) -> int:
    return text[:idx].count("\n") + 1


def finding(
    findings: list[dict[str, Any]],
    rule: str,
    file: str,
    line: int,
    message: str,
    fix: str,
    severity: str = "error",
    source: str = "sky-haven",
) -> None:
    findings.append(
        {
            "rule": rule,
            "file": file,
            "line": line,
            "severity": severity,
            "source": source,
            "finding": message,
            "fix": fix,
        }
    )


def matching_brace_end(text: str, open_brace_idx: int) -> int:
    depth = 0
    in_string = False
    escaped = False
    i = open_brace_idx
    while i < len(text):
        char = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return len(text)


def parse_labels(labels_raw: str) -> list[str]:
    return re.findall(r'"([^"]+)"', labels_raw)


def parse_blocks(text: str, file: str) -> list[Block]:
    blocks: list[Block] = []
    for match in TOP_LEVEL_BLOCK_RE.finditer(text):
        if match.group("indent"):
            continue
        open_brace_idx = text.find("{", match.start())
        end = matching_brace_end(text, open_brace_idx)
        blocks.append(
            Block(
                kind=match.group("kind"),
                labels=parse_labels(match.group("labels")),
                start=match.start(),
                end=end,
                line=line_no(text, match.start()),
                text=text[match.start() : end],
                file=file,
            )
        )
    return blocks


def first_assignment_value(block: str, name: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*(.+)$", block)
    return match.group(1).strip() if match else None


def has_top_level_assignment(block: str, name: str) -> bool:
    return re.search(rf"(?m)^\s*{re.escape(name)}\s*=", block) is not None


def ensure_lock_file(root: Path, infra: Path, generate: bool) -> dict[str, Any]:
    lock = infra / ".terraform.lock.hcl"
    default = {
        "path": "infra/.terraform.lock.hcl",
        "present": lock.exists(),
        "generated": False,
        "attempted_generation": False,
    }
    if lock.exists() or not generate:
        return default
    if not infra.exists():
        return default | {"error": "infra directory missing"}
    try:
        result = subprocess.run(
            ["terraform", f"-chdir={infra}", "init", "-backend=false", "-input=false"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except FileNotFoundError:
        return default | {"attempted_generation": True, "error": "terraform executable not found"}
    except subprocess.TimeoutExpired:
        return default | {"attempted_generation": True, "error": "terraform init -backend=false timed out"}
    return default | {
        "present": lock.exists(),
        "generated": lock.exists(),
        "attempted_generation": True,
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }


def minor_pessimistic_constraint(value: str) -> bool:
    return re.search(r'~>\s*\d+\.\d+(?:["\s,}]|$)', value) is not None


def terraform_version_constraint_ok(value: str) -> bool:
    return "~> 1.9.0" in value


def module_source_requires_version(source_value: str | None) -> bool:
    if source_value is None:
        return False
    source = source_value.strip().strip('"')
    return not (
        source.startswith("./")
        or source.startswith("../")
        or source.startswith("/")
        or source.startswith("git::")
        or source.startswith("github.com/")
        or source.startswith("bitbucket.org/")
    )


def is_taggable_azurerm_resource(resource_type: str) -> bool:
    if not resource_type.startswith("azurerm_"):
        return False
    if resource_type in AZURERM_NOT_TAGGABLE_EXACT:
        return False
    return not any(resource_type.startswith(prefix) for prefix in AZURERM_NOT_TAGGABLE_PREFIXES)


def code_without_declarations(texts: dict[str, str]) -> str:
    stripped_parts: list[str] = []
    for rel, text in texts.items():
        remaining = text
        for block in reversed(parse_blocks(text, rel)):
            if block.kind in {"variable", "output", "locals", "data"}:
                remaining = remaining[: block.start] + "\n" * remaining[block.start : block.end].count("\n") + remaining[block.end :]
        stripped_parts.append(remaining)
    return "\n".join(stripped_parts)


def check_paths(root: Path, tf_files: list[Path], tfvars_files: list[Path], findings: list[dict[str, Any]]) -> None:
    for file in tf_files:
        rel = rel_path(root, file)
        if not rel.startswith("infra/"):
            finding(findings, "paths.tf-under-infra", rel, 1, ".tf file outside infra/", "Move Terraform files under infra/.")
    for file in tfvars_files:
        rel = rel_path(root, file)
        if not rel.startswith("infra/vars/"):
            finding(findings, "paths.tfvars-under-infra-vars", rel, 1, ".tfvars file outside infra/vars/", "Move .tfvars files under infra/vars/.")


def check_core_block_files(infra: Path, all_blocks: list[Block], findings: list[dict[str, Any]]) -> None:
    required = {
        "terraform": "_terraform.tf",
        "provider": "_providers.tf",
        "variable": "_variables.tf",
        "output": "_outputs.tf",
        "locals": "_locals.tf",
        "data": "_data.tf",
    }
    present_kinds = {block.kind for block in all_blocks}
    for kind, filename in required.items():
        if kind in present_kinds and not (infra / filename).exists():
            finding(
                findings,
                "files.core-block-file",
                f"infra/{filename}",
                1,
                f"Required core block file missing for {kind} blocks.",
                f"Move {kind} blocks into infra/{filename}, or create that file if the blocks are intentionally present.",
            )


def check_blank_lines(texts: dict[str, str], blocks_by_file: dict[str, list[Block]], findings: list[dict[str, Any]]) -> None:
    for rel, blocks in blocks_by_file.items():
        text = texts[rel]
        for current, nxt in zip(blocks, blocks[1:]):
            between = text[current.end : nxt.start]
            blank_lines = between.count("\n") - 1
            if blank_lines != 1:
                finding(
                    findings,
                    "style.one-blank-line-between-blocks",
                    rel,
                    line_no(text, current.end),
                    f"Expected exactly one blank line between top-level blocks; found {max(blank_lines, 0)}.",
                    "Run terraform fmt, then leave exactly one empty line between adjacent top-level blocks.",
                    source="hashicorp+sky-haven",
                )


def check_commented_blocks(texts: dict[str, str], findings: list[dict[str, Any]]) -> None:
    for rel, text in texts.items():
        for match in re.finditer(r"(?m)^\s*#\s*(resource|variable|output|locals|data|module|provider)\b", text):
            finding(
                findings,
                "dead-code.commented-terraform-block",
                rel,
                line_no(text, match.start()),
                "Commented-out Terraform block detected.",
                "Delete dead Terraform blocks; rely on git history instead of commented-out code.",
            )


def check_versions(all_blocks: list[Block], findings: list[dict[str, Any]]) -> None:
    terraform_blocks = [block for block in all_blocks if block.kind == "terraform"]
    for block in terraform_blocks:
        required_version = first_assignment_value(block.text, "required_version")
        if required_version is None:
            finding(
                findings,
                "versions.terraform-required-version",
                block.file,
                block.line,
                "Terraform block does not set required_version.",
                'Add required_version = "~> 1.9.0" to the terraform block.',
                source="hashicorp+sky-haven",
            )
        elif not terraform_version_constraint_ok(required_version):
            finding(
                findings,
                "versions.terraform-required-version",
                block.file,
                block.line,
                f"Terraform required_version is not the house baseline '~> 1.9.0': {required_version}",
                'Set required_version = "~> 1.9.0", or update the skill baseline deliberately.',
            )
        provider_blocks = re.finditer(r"(?ms)^\s{2,}([A-Za-z0-9_-]+)\s*=\s*{(?P<body>.*?^\s{2,}})", block.text)
        for provider_match in provider_blocks:
            provider_name = provider_match.group(1)
            provider_body = provider_match.group("body")
            version_value = first_assignment_value(provider_body, "version")
            source_value = first_assignment_value(provider_body, "source")
            line = block.line + block.text[: provider_match.start()].count("\n")
            if source_value is None:
                finding(
                    findings,
                    "versions.provider-source",
                    block.file,
                    line,
                    f"Required provider {provider_name} does not set source.",
                    f"Set an explicit source for provider {provider_name}.",
                    source="hashicorp+sky-haven",
                )
            if version_value is None:
                finding(
                    findings,
                    "versions.provider-version",
                    block.file,
                    line,
                    f"Required provider {provider_name} does not set version.",
                    f'Set a minor-level pessimistic version constraint, for example version = "~> X.Y".',
                    source="hashicorp+sky-haven",
                )
            elif not minor_pessimistic_constraint(version_value):
                finding(
                    findings,
                    "versions.provider-version",
                    block.file,
                    line,
                    f"Provider {provider_name} version is not a minor-level '~>' constraint: {version_value}",
                    f'Set a minor-level pessimistic constraint, for example version = "~> X.Y".',
                )
    for block in [candidate for candidate in all_blocks if candidate.kind == "module"]:
        module_name = block.labels[0] if block.labels else "<unknown>"
        source_value = first_assignment_value(block.text, "source")
        version_value = first_assignment_value(block.text, "version")
        if module_source_requires_version(source_value) and version_value is None:
            finding(
                findings,
                "versions.module-version",
                block.file,
                block.line,
                f"Registry module {module_name} does not set version.",
                f"Set an explicit version for module {module_name}.",
                source="hashicorp",
            )


def check_variables_and_outputs(
    all_blocks: list[Block],
    texts: dict[str, str],
    tfvars_texts: dict[str, str],
    findings: list[dict[str, Any]],
) -> None:
    usage_text = code_without_declarations(texts)
    tfvars_assignments = set()
    for text in tfvars_texts.values():
        tfvars_assignments.update(match.group(1) for match in ASSIGNMENT_RE.finditer(text))

    for block in all_blocks:
        if block.kind == "variable":
            name = block.labels[0]
            if not has_top_level_assignment(block.text, "type"):
                finding(
                    findings,
                    "variables.type",
                    block.file,
                    block.line,
                    f"Variable {name} has no type constraint.",
                    f"Add an explicit type constraint to variable {name}.",
                    source="hashicorp+sky-haven",
                )
            if not has_top_level_assignment(block.text, "description"):
                finding(
                    findings,
                    "variables.description",
                    block.file,
                    block.line,
                    f"Variable {name} has no description.",
                    f"Add a concise description to variable {name}.",
                    source="hashicorp",
                )
            has_default = has_top_level_assignment(block.text, "default")
            if not has_default and name not in tfvars_assignments:
                finding(
                    findings,
                    "variables.required-supplied",
                    block.file,
                    block.line,
                    f"Required variable {name} is not supplied by any .tfvars file.",
                    f"Supply {name} in infra/vars/*.tfvars, or document that it is supplied by pipeline -var or TF_VAR_{name}.",
                    severity="warning",
                )
            if not re.search(rf"\bvar\.{re.escape(name)}\b", usage_text):
                finding(
                    findings,
                    "dead-code.unused-variable",
                    block.file,
                    block.line,
                    f"Variable {name} appears to be unused.",
                    f"Delete variable {name}, or reference it where needed.",
                )
        elif block.kind == "output":
            name = block.labels[0]
            if not has_top_level_assignment(block.text, "description"):
                finding(
                    findings,
                    "outputs.description",
                    block.file,
                    block.line,
                    f"Output {name} has no description.",
                    f"Add a concise description to output {name}.",
                    source="hashicorp",
                )


def check_locals(all_blocks: list[Block], texts: dict[str, str], findings: list[dict[str, Any]]) -> None:
    locals_blocks = [block for block in all_blocks if block.kind == "locals"]
    locals_text = "\n".join(block.text for block in locals_blocks)
    usage_text = code_without_declarations(texts)
    required_names = ["resource_suffix", "resource_suffix_flat"]
    for name in required_names:
        if not re.search(rf"(?m)^\s*{re.escape(name)}\s*=", locals_text):
            finding(
                findings,
                "locals.required",
                "infra/_locals.tf",
                1,
                f"Required local {name} is missing.",
                f"Define local.{name} in infra/_locals.tf.",
            )
    if "managed-by" not in locals_text:
        finding(
            findings,
            "locals.required-tags",
            "infra/_locals.tf",
            1,
            "Required tag local.tags.managed-by is missing.",
            'Define local.tags with a "managed-by" key.',
        )
    local_names = set()
    for block in locals_blocks:
        local_names.update(
            match.group(1)
            for match in re.finditer(r"(?m)^[ \t]{2}([A-Za-z_][A-Za-z0-9_-]*)\s*=", block.text)
        )
    for name in sorted(local_names - {"tags"}):
        if name in required_names:
            continue
        if not re.search(rf"\blocal\.{re.escape(name)}\b", usage_text):
            first_block = locals_blocks[0] if locals_blocks else None
            finding(
                findings,
                "dead-code.unused-local",
                first_block.file if first_block else "infra/_locals.tf",
                first_block.line if first_block else 1,
                f"Local {name} appears to be unused.",
                f"Delete local.{name}, or reference it where needed.",
            )


def check_data_sources(all_blocks: list[Block], texts: dict[str, str], findings: list[dict[str, Any]]) -> None:
    usage_text = code_without_declarations(texts)
    for block in all_blocks:
        if block.kind != "data" or len(block.labels) < 2:
            continue
        data_type, name = block.labels[0], block.labels[1]
        if not re.search(rf"\bdata\.{re.escape(data_type)}\.{re.escape(name)}\b", usage_text):
            finding(
                findings,
                "dead-code.unused-data-source",
                block.file,
                block.line,
                f"Data source data.{data_type}.{name} appears to be unused.",
                f"Delete data.{data_type}.{name}, or reference it where needed.",
            )


def check_resources(all_blocks: list[Block], findings: list[dict[str, Any]]) -> None:
    for block in all_blocks:
        if block.kind != "resource" or len(block.labels) < 2:
            continue
        resource_type, resource_name = block.labels[0], block.labels[1]
        if resource_type == "azurerm_resource_group" and not block.file.endswith("resource-groups.tf"):
            finding(
                findings,
                "files.resource-groups-dedicated-file",
                block.file,
                block.line,
                "Azure resource groups must be defined in resource-groups.tf.",
                "Move azurerm_resource_group resources into infra/resource-groups.tf.",
            )
        if resource_type in {"azurerm_role_assignment", "azurerm_role_definition"} and not block.file.endswith("rbac.tf"):
            finding(
                findings,
                "files.rbac-dedicated-file",
                block.file,
                block.line,
                "Azure RBAC resources must be defined in rbac.tf.",
                "Move Azure RBAC resources into infra/rbac.tf.",
            )
        count_value = first_assignment_value(block.text, "count")
        if count_value is not None and ("?" not in count_value or ":" not in count_value):
            finding(
                findings,
                "meta-arguments.prefer-for-each",
                block.file,
                block.line,
                "Non-conditional count detected; prefer for_each.",
                "Use for_each for multiple named instances; reserve count for simple conditional toggles.",
                source="hashicorp+sky-haven",
            )
        if is_taggable_azurerm_resource(resource_type):
            tags_value = first_assignment_value(block.text, "tags")
            if tags_value is None:
                finding(
                    findings,
                    "tags.required",
                    block.file,
                    block.line,
                    f"{resource_type}.{resource_name} appears taggable but has no tags assignment.",
                    "Set tags = local.tags or tags = merge(local.tags, ...).",
                )
            elif "local.tags" not in tags_value:
                finding(
                    findings,
                    "tags.local-tags",
                    block.file,
                    block.line,
                    f"{resource_type}.{resource_name} tags do not include local.tags.",
                    "Use tags = local.tags or tags = merge(local.tags, ...).",
                )
        name_value = first_assignment_value(block.text, "name")
        if name_value is not None and resource_type.startswith("azurerm_"):
            expected_prefixes = CAF_PREFIXES.get(resource_type, ())
            if expected_prefixes and not any(prefix in name_value for prefix in expected_prefixes):
                expected_prefix_text = ", ".join(expected_prefixes)
                finding(
                    findings,
                    "naming.caf-prefix",
                    block.file,
                    block.line,
                    f"{resource_type}.{resource_name} name does not contain an expected CAF prefix ({expected_prefix_text}).",
                    f"Use one of the CAF prefixes ({expected_prefix_text}) in the resource name expression, unless there is a documented exception.",
                    severity="warning",
                )
            suffix_required = "resource_suffix_flat" if resource_type in {"azurerm_storage_account", "azurerm_container_registry"} else "resource_suffix"
            if f"local.{suffix_required}" not in name_value:
                finding(
                    findings,
                    "naming.resource-suffix",
                    block.file,
                    block.line,
                    f"{resource_type}.{resource_name} name does not use local.{suffix_required}.",
                    f"Include local.{suffix_required} in the resource name expression.",
                )


def check_tfvars(root: Path, tfvars_files: list[Path], tfvars_texts: dict[str, str], findings: list[dict[str, Any]]) -> None:
    for file in tfvars_files:
        rel = rel_path(root, file)
        text = tfvars_texts[rel]
        if not text.strip():
            continue
        lines = text.splitlines()
        has_valid_header = any(AREA_HEADER_RE.match(line) for line in lines)
        if not has_valid_header:
            finding(
                findings,
                "tfvars.area-headers",
                rel,
                1,
                "Missing exact tfvars area comment block header.",
                "Group assignments under headers matching: 41 hashes, space, uppercase title, space, 41 hashes.",
            )
        seen_header = False
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                if AREA_HEADER_RE.match(line):
                    seen_header = True
                continue
            if "=" in line and not seen_header:
                finding(
                    findings,
                    "tfvars.assignments-under-area-headers",
                    rel,
                    idx,
                    "tfvars assignment appears before the first valid area header.",
                    "Move the assignment below an exact uppercase area header.",
                )
            assignment = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*=", line)
            if assignment and SECRET_NAME_RE.search(assignment.group(1)):
                finding(
                    findings,
                    "tfvars.no-secrets",
                    rel,
                    idx,
                    f"tfvars key {assignment.group(1)} looks secret-bearing.",
                    "Do not commit secrets in .tfvars; supply them through secure pipeline variables, TF_VAR_*, Key Vault, or equivalent.",
                    severity="warning",
                    source="hashicorp+sky-haven",
                )


def check_gitignore(root: Path, findings: list[dict[str, Any]]) -> None:
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        finding(
            findings,
            "repo.gitignore-terraform",
            ".gitignore",
            1,
            ".gitignore is missing; Terraform cache and plan files may be committed accidentally.",
            "Create .gitignore entries for .terraform/, *.tfstate*, *.tfplan, and crash logs.",
            severity="warning",
            source="hashicorp",
        )
        return
    text = read_text(gitignore)
    required_patterns = [".terraform", "*.tfstate", "*.tfstate.*", "*.tfplan", "crash.log"]
    for pattern in required_patterns:
        if pattern not in text:
            finding(
                findings,
                "repo.gitignore-terraform",
                ".gitignore",
                1,
                f".gitignore does not include Terraform pattern {pattern}.",
                f"Add {pattern} to .gitignore unless handled by a global ignore.",
                severity="warning",
                source="hashicorp",
            )


def inspect(target: str, ensure_lock: bool) -> dict[str, Any]:
    root = target_dir(target)
    infra = root / "infra"
    tf_files = sorted(
        [path for path in root.rglob("*.tf") if ".terraform" not in path.parts],
        key=lambda path: rel_path(root, path),
    )
    tfvars_files = sorted(
        [path for path in root.rglob("*.tfvars") if ".terraform" not in path.parts],
        key=lambda path: rel_path(root, path),
    )
    texts = {rel_path(root, path): read_text(path) for path in tf_files}
    tfvars_texts = {rel_path(root, path): read_text(path) for path in tfvars_files}
    blocks_by_file = {rel: parse_blocks(text, rel) for rel, text in texts.items()}
    all_blocks = [block for blocks in blocks_by_file.values() for block in blocks]
    findings: list[dict[str, Any]] = []

    has_terraform = bool(tf_files or tfvars_files or infra.exists())
    lock_file = ensure_lock_file(root, infra, ensure_lock) if has_terraform else {
        "path": "infra/.terraform.lock.hcl",
        "present": False,
        "generated": False,
        "attempted_generation": False,
        "skipped": "no Terraform files or infra directory found",
    }
    if not has_terraform:
        return {
            "target": str(root),
            "tf_files": 0,
            "tfvars_files": 0,
            "terraform_lock_file": lock_file,
            "finding_count": 0,
            "findings": [],
            "llm_tasks": [],
        }
    if has_terraform and not lock_file.get("present"):
        finding(
            findings,
            "repo.lock-file",
            "infra/.terraform.lock.hcl",
            1,
            "Terraform lock file is missing.",
            "Run terraform -chdir=infra init -backend=false -input=false, review the generated lock file, and commit infra/.terraform.lock.hcl.",
            source="hashicorp+sky-haven",
        )

    check_paths(root, tf_files, tfvars_files, findings)
    check_core_block_files(infra, all_blocks, findings)
    check_blank_lines(texts, blocks_by_file, findings)
    check_commented_blocks(texts, findings)
    check_versions(all_blocks, findings)
    check_variables_and_outputs(all_blocks, texts, tfvars_texts, findings)
    check_locals(all_blocks, texts, findings)
    check_data_sources(all_blocks, texts, findings)
    check_resources(all_blocks, findings)
    check_tfvars(root, tfvars_files, tfvars_texts, findings)
    if has_terraform:
        check_gitignore(root, findings)

    findings.sort(key=lambda item: (item["file"], item["line"], item["rule"], item["finding"]))
    return {
        "target": str(root),
        "tf_files": len(tf_files),
        "tfvars_files": len(tfvars_files),
        "terraform_lock_file": lock_file,
        "finding_count": len(findings),
        "findings": findings,
        "llm_tasks": [
            "judge whether resource files are grouped by functional purpose beyond the deterministic dedicated-file checks",
            "confirm CAF abbreviations where the helper has no mapping or where a repository has documented naming exceptions",
            "confirm required variables supplied externally by CI/CD -var or TF_VAR_* when they are intentionally absent from .tfvars",
            "review false positives from taggable Azure resource detection against the provider version in use",
            "plan safe auto-fixes after reporting; do not move/delete files or rewrite Terraform without explicit approval",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--target", required=True)
    inspect_parser.add_argument("--json", action="store_true")
    inspect_parser.add_argument(
        "--ensure-lock",
        action="store_true",
        help="Idempotently run terraform init -backend=false -input=false when infra/.terraform.lock.hcl is missing.",
    )
    args = parser.parse_args(argv)
    try:
        if args.cmd == "inspect":
            out(inspect(args.target, args.ensure_lock))
        return 0
    except SkillError as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
