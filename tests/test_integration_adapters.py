"""Testes de integração dos adaptadores reais (ADR-0014) contra o compose de `dev/`.

Pulados por padrão. Para rodar: `docker compose -f dev/docker-compose.yml up -d s3 rabbitmq` e
`INTEGRATION=1 pipenv run python -m unittest tests.test_integration_adapters -v`.
"""
import os
import unittest
import uuid

ENABLED = os.getenv("INTEGRATION") == "1"
S3_ENV = {"STORAGE_DRIVER": "s3", "S3_ENDPOINT": "http://localhost:9000", "S3_BUCKET": "raw-profiles",
          "S3_ACCESS_KEY": "dev", "S3_SECRET_KEY": "dev"}
AMQP_URL = os.getenv("AMQP_URL", "amqp://guest:guest@localhost:5672/")


@unittest.skipUnless(ENABLED, "defina INTEGRATION=1 com o compose de dev/ no ar")
class S3StorageTest(unittest.TestCase):
    def setUp(self):
        import infra
        self.storage = infra.new_storage(S3_ENV)
        self.key = f"test/{uuid.uuid4().hex}.zip"

    def test_put_get(self):
        self.storage.put(self.key, b"zip")
        self.assertEqual(self.storage.get(self.key), b"zip")

    def test_never_overwrites(self):
        self.storage.put(self.key, b"1")
        with self.assertRaises(FileExistsError):
            self.storage.put(self.key, b"2")
        self.assertEqual(self.storage.get(self.key), b"1")

    def test_missing_key(self):
        with self.assertRaises(FileNotFoundError):
            self.storage.get(self.key)


@unittest.skipUnless(ENABLED, "defina INTEGRATION=1 com o compose de dev/ no ar")
class RabbitMQQueueTest(unittest.TestCase):
    def setUp(self):
        from infra.rabbitmq import RabbitMQQueue
        self.topic = f"test-{uuid.uuid4().hex[:8]}"
        self.queue = RabbitMQQueue(AMQP_URL, max_attempts=3, backoff=lambda attempt: 0, idle_timeout=2)

    def tearDown(self):
        import pika
        with pika.BlockingConnection(pika.URLParameters(AMQP_URL)) as conn:
            ch = conn.channel()
            ch.queue_delete(self.topic)
            ch.queue_delete(f"{self.topic}.dlq")

    def test_publish_consume_ack(self):
        got = []
        self.queue.publish(self.topic, b"a")
        self.queue.publish(self.topic, b"b")
        self.queue.consume(self.topic, lambda m: got.append((m.body, m.attempt)))
        self.assertEqual(got, [(b"a", 1), (b"b", 1)])

    def test_redelivery_increments_attempt_until_success(self):
        attempts = []

        def handle(msg):
            attempts.append(msg.attempt)
            if msg.attempt < 3:
                raise RuntimeError("transitório")

        self.queue.publish(self.topic, b"x")
        self.queue.consume(self.topic, handle)
        self.assertEqual(attempts, [1, 2, 3])

    def test_dead_letter_after_max_attempts(self):
        attempts = []

        def handle(msg):
            attempts.append(msg.attempt)
            raise RuntimeError("boom")

        self.queue.publish(self.topic, b"x")
        self.queue.consume(self.topic, handle)
        self.assertEqual(attempts, [1, 2, 3])
        import pika
        with pika.BlockingConnection(pika.URLParameters(AMQP_URL)) as conn:
            method, _, body = conn.channel().basic_get(f"{self.topic}.dlq", auto_ack=True)
        self.assertIsNotNone(method, "mensagem não chegou à DLQ")
        self.assertEqual(body, b"x")


if __name__ == "__main__":
    unittest.main()
