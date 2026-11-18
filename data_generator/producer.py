"""
Kafka streaming producer for transactions (topic: txn.raw).
"""

import json
import logging
import time

from data_generator.entities import Transaction

logger = logging.getLogger("sentraflow-stream-producer")


class KafkaStreamProducer:
    """
    Publishes streaming transactions to Kafka topic txn.raw.
    Falls back gracefully if Kafka is offline.
    """

    def __init__(
        self, bootstrap_servers: str = "localhost:9092", topic: str = "txn.raw"
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.producer = None
        self._init_producer()

    def _init_producer(self):
        try:
            # Attempt lazy import of kafka-python or confluent-kafka
            from kafka import KafkaProducer

            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                retries=3,
            )
            logger.info(f"Connected to Kafka at {self.bootstrap_servers}")
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"Kafka unavailable ({e}). Producer operating in mock/dry-run mode."
            )
            self.producer = None

    def publish_transaction(self, txn: Transaction) -> bool:
        """
        Publishes a single transaction.
        """
        payload = txn.model_dump()
        if self.producer:
            try:
                self.producer.send(self.topic, value=payload)
                return True
            except Exception as e:  # noqa: BLE001
                logger.error(f"Failed to publish txn {txn.txn_id} to Kafka: {e}")
                return False
        return True  # Successful dry-run

    def stream_transactions(
        self,
        transactions: list[Transaction],
        events_per_second: float = 10.0,
        max_events: int | None = None,
    ) -> int:
        """
        Streams a list of transactions at the configured rate.
        """
        delay = 1.0 / max(events_per_second, 0.1)
        count = 0

        for txn in transactions:
            if max_events and count >= max_events:
                break
            self.publish_transaction(txn)
            count += 1
            time.sleep(delay)

        if self.producer:
            self.producer.flush()

        return count
