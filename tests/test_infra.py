import tempfile
import unittest

import infra


class MemoryQueueTest(unittest.TestCase):
    def test_delivers_and_acks(self):
        q, got = infra.MemoryQueue(), []
        q.publish("parse", b"a")
        q.publish("parse", b"b")
        q.consume("parse", lambda m: got.append(m.body))
        self.assertEqual(got, [b"a", b"b"])

    def test_redelivers_on_error_then_dead_letters(self):
        q, attempts = infra.MemoryQueue(max_attempts=3), []

        def handle(msg):
            attempts.append(msg.attempt)
            raise RuntimeError("boom")

        q.publish("parse", b"x")
        q.consume("parse", handle)
        self.assertEqual(attempts, [1, 2, 3])
        self.assertEqual([m.body for m in q.dead_letters["parse"]], [b"x"])

    def test_retry_succeeds(self):
        q, seen = infra.MemoryQueue(), []

        def handle(msg):
            seen.append(msg.attempt)
            if msg.attempt < 2:
                raise RuntimeError("transitório")

        q.publish("parse", b"x")
        q.consume("parse", handle)
        self.assertEqual(seen, [1, 2])
        self.assertEqual(q.dead_letters["parse"], [])


class DeferTest(unittest.TestCase):
    def test_defer_does_not_count_as_failure(self):
        q, calls = infra.MemoryQueue(max_attempts=2), []

        def handle(msg):
            calls.append(msg.attempt)
            raise infra.Defer(60, "limite de ritmo")

        q.publish("collect", b"x")
        q.consume("collect", handle)
        self.assertEqual(calls, [1])                       # não é reentregue no mesmo ciclo
        self.assertEqual(q.dead_letters["collect"], [])    # e nunca vai para a DLQ
        self.assertEqual([(m.body, m.attempt, d) for m, d in q.deferred["collect"]], [(b"x", 1, 60)])

    def test_released_deferred_message_keeps_attempt_and_is_redelivered(self):
        q, seen = infra.MemoryQueue(), []
        q.publish("collect", b"x")
        q.consume("collect", lambda m: (_ for _ in ()).throw(infra.Defer(5)))
        q.release_deferred("collect")
        q.consume("collect", lambda m: seen.append((m.body, m.attempt)))
        self.assertEqual(seen, [(b"x", 1)])
        self.assertEqual(q.deferred["collect"], [])

    def test_defer_carries_delay(self):
        self.assertEqual(infra.Defer(12.5).delay, 12.5)


class FsStorageTest(unittest.TestCase):
    def test_put_get_and_immutability(self):
        with tempfile.TemporaryDirectory() as d:
            s = infra.FsStorage(d)
            s.put("raw/fulano/1.zip", b"zip")
            self.assertEqual(s.get("raw/fulano/1.zip"), b"zip")
            with self.assertRaises(FileExistsError):
                s.put("raw/fulano/1.zip", b"outro")

    def test_rejects_key_outside_root(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                infra.FsStorage(d).put("../fora.zip", b"x")


class FactoryTest(unittest.TestCase):
    def test_defaults(self):
        self.assertIsInstance(infra.new_storage({}), infra.FsStorage)
        self.assertIsNone(infra.new_queue({}))

    def test_memory_queue(self):
        self.assertIsInstance(infra.new_queue({"QUEUE_DRIVER": "memory"}), infra.MemoryQueue)

    def test_unknown_driver_fails_loudly(self):
        for factory, env in ((infra.new_storage, {"STORAGE_DRIVER": "gcs"}), (infra.new_queue, {"QUEUE_DRIVER": "sqs"})):
            with self.assertRaises(ValueError):
                factory(env)

    def test_real_drivers_require_their_variables(self):
        with self.assertRaisesRegex(ValueError, "S3_BUCKET"):
            infra.new_storage({"STORAGE_DRIVER": "s3"})
        with self.assertRaisesRegex(ValueError, "AMQP_URL"):
            infra.new_queue({"QUEUE_DRIVER": "rabbitmq"})


if __name__ == "__main__":
    unittest.main()
