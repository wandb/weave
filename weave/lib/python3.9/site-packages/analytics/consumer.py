import logging
from threading import Thread

from analytics.version import VERSION
from analytics.request import post

try:
    from queue import Empty
except:
    from Queue import Empty

class Consumer(Thread):
    """Consumes the messages from the client's queue."""
    log = logging.getLogger('segment')

    def __init__(self, queue, write_key, upload_size=100, host=None, on_error=None):
        """Create a consumer thread."""
        Thread.__init__(self)
        # Make consumer a daemon thread so that it doesn't block program exit
        self.daemon = True
        self.upload_size = upload_size
        self.write_key = write_key
        self.host = host
        self.on_error = on_error
        self.queue = queue
        # It's important to set running in the constructor: if we are asked to
        # pause immediately after construction, we might set running to True in
        # run() *after* we set it to False in pause... and keep running forever.
        self.running = True
        self.retries = 3

    def run(self):
        """Runs the consumer."""
        self.log.debug('consumer is running...')
        while self.running:
            self.upload()

        self.log.debug('consumer exited.')

    def pause(self):
        """Pause the consumer."""
        self.running = False

    def upload(self):
        """Upload the next batch of items, return whether successful."""
        success = False
        batch = self.next()
        if len(batch) == 0:
            return False

        try:
            self.request(batch)
            success = True
        except Exception as e:
            self.log.error('error uploading: %s', e)
            success = False
            if self.on_error:
                self.on_error(e, batch)
        finally:
            # mark items as acknowledged from queue
            for item in batch:
                self.queue.task_done()
            return success

    def next(self):
        """Return the next batch of items to upload."""
        queue = self.queue
        items = []

        while len(items) < self.upload_size:
            try:
                item = queue.get(block=True, timeout=0.5)
                items.append(item)
            except Empty:
                break

        return items

    def request(self, batch, attempt=0):
        """Attempt to upload the batch and retry before raising an error """
        try:
            post(self.write_key, self.host, batch=batch)
        except:
            if attempt > self.retries:
                raise
            self.request(batch, attempt+1)
