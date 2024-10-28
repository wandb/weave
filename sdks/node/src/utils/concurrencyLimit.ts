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
    if (this.queue.length > 0 && this.activeCount < this.limit) {
      const nextTask = this.queue.shift();
      this.activeCount++;
      nextTask!();
    }
  }

  limitFunction<T extends any[], R>(
    asyncFn: (...args: T) => Promise<R>
  ): (...args: T) => Promise<R> {
    return async (...args: T): Promise<R> => {
      return new Promise<R>((resolve, reject) => {
        const task = async () => {
          try {
            const result = await asyncFn(...args);
            resolve(result);
          } catch (e) {
            reject(e);
          } finally {
            this.activeCount--;
            this.tryExecuteNext();
          }
        };

        if (this.activeCount < this.limit) {
          this.activeCount++;
          task();
        } else {
          this.queue.push(task);
        }
      });
    };
  }
}
