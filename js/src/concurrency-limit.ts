export class ConcurrencyLimiter {
  private activeCount = 0;
  private queue: (() => void)[] = [];

  constructor(private limit: number) {}

  get active(): number {
    return this.activeCount;
  }

  get pending(): number {
    return this.queue.length;
  }

  private tryExecuteNext() {
    if (this.pending && this.active < this.limit) {
      const nextTask = this.queue.shift();
      this.activeCount++;
      Promise.resolve(nextTask!())
        .catch(error => {
          console.error('Failed to execute task:', error);
        })
        .finally(() => {
          this.activeCount--;
          this.tryExecuteNext();
        });
    }
  }

  limitFunction<T extends any[], R>(asyncFn: (...args: T) => Promise<R>): (...args: T) => Promise<R> {
    return async (...args: T): Promise<R> => {
      return new Promise<R>((resolve, reject) => {
        const task = async () => {
          try {
            const result = await asyncFn(...args);
            resolve(result);
          } catch (error) {
            reject(error);
          }
        };

        if (this.active < this.limit) {
          this.activeCount++;
          task();
        } else {
          this.queue.push(task);
        }
      });
    };
  }
}
