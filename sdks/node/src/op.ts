import {Call, InternalCall} from './call';
import {getGlobalClient} from './clientApi';
import {TRACE_CALL_EMOJI} from './constants';
import {Op, OpOptions, OpRef, CallMethod} from './opType';
import {getGlobalDomain} from './urls';
import {warnOnce} from './utils/warnOnce';

export interface MethodDecoratorContext {
  kind: 'method';
  name: string | symbol;
  static?: boolean;
  class?: Function;
  addInitializer?(initializer: () => void): void;
  private?: boolean;
  access?: {
    has(object: object): boolean;
    get(object: object): Function;
  };
  metadata?: any;
}

/**
 * Checks if the arguments match the signature of a Stage 3 decorator.
 */
function isModernDecorator(
  args: any[]
): args is [Function, MethodDecoratorContext] {
  return (
    args.length === 2 &&
    args[1] &&
    typeof args[1] === 'object' &&
    'kind' in args[1] &&
    args[1].kind === 'method' // Must be the decorator context kind, not OpOptions.kind
  );
}

/**
 * Checks if the arguments match the signature of a Legacy decorator.
 */
function isLegacyDecorator(
  args: any[]
): args is [Object, string | symbol, TypedPropertyDescriptor<any>] {
  return (
    args.length === 3 &&
    (typeof args[0] === 'object' || typeof args[0] === 'function') &&
    (typeof args[1] === 'string' || typeof args[1] === 'symbol') &&
    typeof args[2] === 'object'
  );
}

/**
 * Checks if the arguments match the signature of a Decorator Factory.
 */
function isDecoratorFactory(args: any[]): args is [Partial<OpOptions<any>>] {
  return (
    args.length === 1 &&
    typeof args[0] === 'object' &&
    !('prototype' in args[0]) && // Distinguish from class constructors
    !('bind' in args[0]) && // Distinguish from functions
    !Array.isArray(args[0])
  );
}

/**
 * Checks if the arguments match the signature of Function Binding.
 */
function isFunctionBinding(
  args: any[]
): args is [any, (...args: any[]) => any, OpOptions<any> | undefined] {
  return args.length >= 2 && typeof args[1] === 'function';
}

/**
 * Type for the options specifically needed by deriveOpName.
 */
type DeriveOpNameOptions = Pick<
  OpOptions<any>,
  'name' | 'originalFunction' | 'bindThis'
>;

/**
 * Derives the name of the wrapped function.
 */
function deriveOpName<T extends (...args: any[]) => any>(
  fn: T,
  options?: Partial<DeriveOpNameOptions>,
  context?: MethodDecoratorContext
): string {
  const fnName = options?.originalFunction?.name || fn.name || 'anonymous';
  let calculatedName = 'anonymous';

  if (options?.name) {
    calculatedName = options.name;
  } else if (context?.kind === 'method' && context.addInitializer) {
    calculatedName = '__pending__';
  } else if (context?.kind === 'method') {
    const className = context.class?.name || 'anonymous';
    calculatedName = `${className}.${String(context.name)}`;
  } else if (options?.bindThis) {
    const className =
      Object.getPrototypeOf(options.bindThis).constructor.name || 'anonymous';
    calculatedName = `${className}.${fnName}`;
  } else {
    calculatedName = fnName;
  }
  return calculatedName;
}

/**
 * Creates the core wrapper function that handles call tracking and name setting.
 */
function createOpWrapper<T extends (...args: any[]) => any>(
  fn: T,
  optionsAndContext: Partial<OpOptions<T>> & {context?: MethodDecoratorContext}
): Op<T> {
  const {context, ...options} = optionsAndContext;

  const call = new InternalCall();

  const opWrapper = async function (
    this: any,
    ...params: Parameters<T>
  ): Promise<Awaited<ReturnType<T>>> {
    const client = getGlobalClient();
    const thisArg =
      options?.isDecorator || options?.shouldAdoptThis
        ? this
        : options?.bindThis;

    if (!client) {
      warnOnce(
        'weave-not-initialized',
        'WARNING: Weave is not initialized, so calls wont be tracked.  Call `weave.init` to initialize before calling ops.  If this is intentional, you can safely ignore this warning.'
      );
      return await fn.apply(thisArg, params);
    }

    const {currentCall, parentCall, newStack} = client.pushNewCall();
    const startTime = new Date();
    if (client.settings.shouldPrintCallLink && parentCall == null) {
      const domain = getGlobalDomain();
      console.log(
        `${TRACE_CALL_EMOJI} https://${domain}/${client.projectId}/r/call/${currentCall.callId}`
      );
    }
    const displayName = options?.callDisplayName
      ? options.callDisplayName(...params)
      : undefined;

    const opRefForCall: Op<any> | OpRef = opWrapper as Op<any>;

    const startCallPromise = client.createCall(
      call,
      opRefForCall,
      params,
      options?.parameterNames,
      thisArg,
      currentCall,
      parentCall,
      startTime,
      displayName
    );

    try {
      let result = await client.runWithCallStack(newStack, async () => {
        return await fn.apply(thisArg, params);
      });

      // Stream handling
      if (
        options?.streamReducer &&
        typeof result === 'object' &&
        result !== null &&
        Symbol.asyncIterator in result
      ) {
        const {initialStateFn, reduceFn, finalizeFn} = options.streamReducer;
        let state = initialStateFn();

        async function* WeaveIterator() {
          try {
            for await (const chunk of result as AsyncIterable<any>) {
              state = reduceFn(state, chunk);
              yield chunk;
            }
          } finally {
            if (client) {
              const endTime = new Date();
              finalizeFn(state);
              await client.finishCall(
                call,
                state,
                currentCall,
                parentCall,
                options?.summarize,
                endTime,
                startCallPromise
              );
            }
          }
        }
        const proxy = new Proxy(result, {
          get: (target, prop) => {
            if (prop === Symbol.asyncIterator) {
              return WeaveIterator;
            }

            // allow all other properties to be accessed normally
            return Reflect.get(target, prop);
          },
        });

        return proxy;
      } else {
        // Non-stream handling
        const endTime = new Date();
        await client.finishCall(
          call,
          result,
          currentCall,
          parentCall,
          options?.summarize,
          endTime,
          startCallPromise
        );
        return result;
      }
    } catch (error) {
      const endTime = new Date();
      await client.finishCallWithException(
        call,
        error,
        currentCall,
        parentCall,
        endTime,
        startCallPromise
      );
      await client.waitForBatchProcessing();
      throw error;
    }
  } as Op<T>;

  // Assign properties to the wrapper
  opWrapper.__name = deriveOpName(fn, options, context);
  opWrapper.__isOp = true as const;
  opWrapper.__wrappedFunction = options?.originalFunction ?? fn;
  opWrapper.__boundThis = options?.bindThis;
  opWrapper.__parameterNames = options?.parameterNames;
  opWrapper.__kind = options?.kind;
  opWrapper.__color = options?.color;

  // We need to hook into modern decorators initializer to set the name
  if (opWrapper.__name === '__pending__' && context?.addInitializer) {
    context.addInitializer(function (this: any) {
      const actualClassName = context.static
        ? this.name
        : this.constructor.name;
      opWrapper.__name = `${actualClassName}.${String(context.name)}`;
    });
  }

  opWrapper.invoke = createCallMethod<T>(opWrapper, call.proxy) as any;

  return opWrapper;
}

// ---------------- Handler Functions ----------------

function handleModernDecorator<T extends (...args: any[]) => any>(
  originalMethod: T,
  context: MethodDecoratorContext,
  factoryOptions?: Partial<OpOptions<T>>
): Op<T> {
  if (context.kind !== 'method') {
    throw new Error(
      '@weave.op currently only supports method decorators (Stage 3)'
    );
  }
  const options = {
    ...factoryOptions,
    isDecorator: true,
    originalFunction: originalMethod,
    context: context,
  };
  const wrapped = createOpWrapper<T>(originalMethod, options);
  return wrapped;
}

function handleLegacyDecorator<T extends (...args: any[]) => any>(
  target: Object,
  propertyKey: string | symbol,
  descriptor: TypedPropertyDescriptor<T>,
  factoryOptions?: Partial<OpOptions<T>>
): TypedPropertyDescriptor<T> {
  const originalFn = descriptor.value;
  if (typeof originalFn !== 'function') {
    throw new Error('@weave.op can only be used to decorate methods');
  }

  // Derive default legacy name
  let className = 'anonymous';
  if (target.constructor === Function) {
    // Static method
    className = (target as Function).name || 'anonymous';
  } else {
    // Instance method
    className = target.constructor?.name || 'anonymous';
  }
  const derivedName = `${className}.${String(propertyKey)}`;

  const options = {
    ...factoryOptions,
    name: factoryOptions?.name || derivedName,
    isDecorator: true,
    originalFunction: originalFn as T,
  };

  const wrapped = createOpWrapper<T>(originalFn as T, options);

  descriptor.value = wrapped as T;
  return descriptor;
}

function handleDecoratorFactory<T extends (...args: any[]) => any>(
  factoryOptions: Partial<OpOptions<T>>
): MethodDecorator | Op<T> {
  return function (...decoratorArgs: any[]): any {
    // Stage 3 Factory Usage
    if (isModernDecorator(decoratorArgs)) {
      const [originalMethod, context] = decoratorArgs as [
        (...args: any[]) => any,
        MethodDecoratorContext,
      ];
      return handleModernDecorator(originalMethod, context, factoryOptions);
    }
    // Legacy Factory Usage
    if (isLegacyDecorator(decoratorArgs)) {
      const [target, propertyKey, descriptor] = decoratorArgs as [
        Object,
        string | symbol,
        TypedPropertyDescriptor<(...args: any[]) => any>,
      ];
      return handleLegacyDecorator(
        target,
        propertyKey,
        descriptor,
        factoryOptions
      );
    }
    throw new Error(
      'Invalid arguments passed to decorator generated by @weave.op factory'
    );
  };
}

function handleFunctionBinding<T extends (...args: any[]) => any>(
  thisArg: any,
  fn: T,
  options?: OpOptions<T>
): Op<T> {
  const boundFn = fn.bind(thisArg);
  // Cast boundFn to T since bind preserves the signature
  return createOpWrapper(boundFn as T, {
    ...options,
    originalFunction: fn,
    bindThis: thisArg,
  });
}

// ---------------- Main `op` Function ----------------

// Function wrapping: const op = weave.op(fn)
export function op<T extends (...args: any[]) => any>(
  fn: T,
  options?: OpOptions<T>
): Op<T>;
// Method binding: const op = weave.op(this, fn)
export function op<T extends (...args: any[]) => any>(
  thisArg: any,
  fn: T,
  options?: OpOptions<T>
): Op<T>;
// Legacy decorator usage (experimentalDecorators in tsconfig.json): @weave.op
export function op(
  target: Object,
  propertyKey: string | symbol,
  descriptor: TypedPropertyDescriptor<any>
): TypedPropertyDescriptor<any>;
// Stage 3 method decorator usage (decorators in tsconfig.json): @weave.op
export function op<T extends (...args: any[]) => any>(
  value: T,
  context: MethodDecoratorContext
): Op<T>;
// Decorator factory usage: @weave.op({ ... })
export function op(options: Partial<OpOptions<any>>): MethodDecorator;
export function op(...args: any[]): any {
  // Stage 3 Decorator
  if (isModernDecorator(args)) {
    const [originalMethod, context] = args;
    // Cast originalMethod to a specific function type before passing
    return handleModernDecorator(
      originalMethod as (...args: any[]) => any,
      context
    );
  }

  // Legacy Decorator
  if (isLegacyDecorator(args)) {
    const [target, propertyKey, descriptor] = args;
    // Legacy decorators modify the descriptor and return it
    return handleLegacyDecorator(target, propertyKey, descriptor);
  }

  // Decorator Factory
  if (isDecoratorFactory(args)) {
    const [options] = args;
    return handleDecoratorFactory(options);
  }

  // Function Binding
  if (isFunctionBinding(args)) {
    const [thisArg, fn, options] = args;
    return handleFunctionBinding(thisArg, fn, options);
  }

  const [fn, options] = args;
  return createOpWrapper<typeof fn>(
    fn,
    typeof options === 'object' ? options : {}
  );
}

export function isOp(fn: any): fn is Op<any> {
  return fn?.__isOp === true;
}

export function createCallMethod<F extends (...args: any[]) => any>(
  opWrapper: (
    this: any,
    ...args: Parameters<F>
  ) => Promise<Awaited<ReturnType<F>>>,
  callProxy: Call
): CallMethod<F> {
  return async function call(this: any, ...args: Parameters<F>) {
    return [await opWrapper.apply(this, args), callProxy] as [
      Awaited<ReturnType<F>>,
      Call,
    ];
  };
}
