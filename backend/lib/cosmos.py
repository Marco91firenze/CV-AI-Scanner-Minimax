"""Azure Cosmos DB helpers with explicit partition keys per container."""

from __future__ import annotations

from typing import Any

from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.container import ContainerProxy
from azure.cosmos.database import DatabaseProxy


def get_database(endpoint: str, key: str, database_name: str) -> DatabaseProxy:
    client = CosmosClient(endpoint, credential=key)
    return client.get_database_client(database_name)


def get_container(db: DatabaseProxy, name: str) -> ContainerProxy:
    return db.get_container_client(name)


def ensure_containers(
    endpoint: str,
    key: str,
    database_name: str,
    companies: str,
    jobs: str,
    cvs: str,
    transactions: str,
) -> DatabaseProxy:
    """Create database and containers if missing (idempotent for dev/bootstrap)."""
    client = CosmosClient(endpoint, credential=key)
    client.create_database_if_not_exists(id=database_name)
    db = client.get_database_client(database_name)
    db.create_container_if_not_exists(id=companies, partition_key=PartitionKey(path="/id"))
    db.create_container_if_not_exists(id=jobs, partition_key=PartitionKey(path="/company_id"))
    db.create_container_if_not_exists(id=cvs, partition_key=PartitionKey(path="/company_id"))
    db.create_container_if_not_exists(
        id=transactions, partition_key=PartitionKey(path="/company_id")
    )
    return db


def query_partition(
    container: ContainerProxy,
    partition_value: str,
    sql: str,
    parameters: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    params = parameters or []
    for item in container.query_items(
        query=sql,
        parameters=params,
        partition_key=partition_value,
        enable_cross_partition_query=False,
    ):
        items.append(item)
    return items
