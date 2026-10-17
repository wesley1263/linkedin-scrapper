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
        with self.assertRaises(ValueError):
            infra.new_storage({"STORAGE_DRIVER": "s3"})
        with self.assertRaises(ValueError):
            infra.new_queue({"QUEUE_DRIVER": "rabbitmq"})


if __name__ == "__main__":
    unittest.main()
