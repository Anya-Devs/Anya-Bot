/**
 * Custom error classes and error handling utilities
 */

export class AppError extends Error {
  constructor(
    message: string,
    public code: string,
    public statusCode: number = 500,
    public isOperational: boolean = true
  ) {
    super(message);
    this.name = this.constructor.name;
    Error.captureStackTrace(this, this.constructor);
  }
}

export class ValidationError extends AppError {
  constructor(message: string) {
    super(message, 'VALIDATION_ERROR', 400);
  }
}

export class NotFoundError extends AppError {
  constructor(resource: string) {
    super(`${resource} not found`, 'NOT_FOUND', 404);
  }
}

export class AuthenticationError extends AppError {
  constructor(message: string = 'Authentication failed') {
    super(message, 'AUTH_ERROR', 401);
  }
}

export class FirebaseError extends AppError {
  constructor(message: string, originalError?: any) {
    super(message, 'FIREBASE_ERROR', 500);
    if (originalError) {
      this.stack = originalError.stack;
    }
  }
}

export class NetworkError extends AppError {
  constructor(message: string = 'Network request failed') {
    super(message, 'NETWORK_ERROR', 503);
  }
}

/**
 * Error handler for async functions
 */
export const asyncHandler = (fn: Function) => {
  return (...args: any[]) => {
    return Promise.resolve(fn(...args)).catch((error) => {
      console.error('Async error:', error);
      throw error;
    });
  };
};

/**
 * Log error to console with formatting
 */
export const logError = (error: Error | AppError, context?: string) => {
  const timestamp = new Date().toISOString();
  const contextStr = context ? `[${context}]` : '';
  
  console.error(`\n${'='.repeat(60)}`);
  console.error(`${timestamp} ${contextStr} ERROR`);
  console.error(`${'='.repeat(60)}`);
  console.error(`Name: ${error.name}`);
  console.error(`Message: ${error.message}`);
  
  if (error instanceof AppError) {
    console.error(`Code: ${error.code}`);
    console.error(`Status: ${error.statusCode}`);
  }
  
  if (error.stack) {
    console.error(`\nStack Trace:\n${error.stack}`);
  }
  console.error(`${'='.repeat(60)}\n`);
};

/**
 * Handle Firebase errors and convert to AppError
 */
export const handleFirebaseError = (error: any): AppError => {
  const errorCode = error.code || 'unknown';
  const errorMessage = error.message || 'An unknown Firebase error occurred';

  switch (errorCode) {
    case 'permission-denied':
      return new AuthenticationError('Permission denied. Please check your authentication.');
    
    case 'not-found':
      return new NotFoundError('Resource');
    
    case 'already-exists':
      return new ValidationError('Resource already exists');
    
    case 'failed-precondition':
      return new ValidationError('Operation failed: precondition not met');
    
    case 'unavailable':
      return new NetworkError('Firebase service temporarily unavailable');
    
    case 'unauthenticated':
      return new AuthenticationError('User not authenticated');
    
    default:
      return new FirebaseError(errorMessage, error);
  }
};

/**
 * Global error handler for React components
 */
export class ErrorBoundary {
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  static logErrorToService(error: Error, _errorInfo: any) {
    logError(error, 'ErrorBoundary');
    // Here you could send to an error tracking service like Sentry
  }
}

/**
 * Format error for user display
 */
export const formatErrorForUser = (error: Error | AppError): string => {
  if (error instanceof AppError && error.isOperational) {
    return error.message;
  }
  
  // Don't expose internal errors to users
  return 'An unexpected error occurred. Please try again later.';
};

/**
 * Retry function with exponential backoff
 */
export const retryWithBackoff = async <T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  baseDelay: number = 1000
): Promise<T> => {
  let lastError: Error;
  
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      
      if (attempt < maxRetries - 1) {
        const delay = baseDelay * Math.pow(2, attempt);
        console.warn(`Attempt ${attempt + 1} failed. Retrying in ${delay}ms...`);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }
  
  throw new AppError(
    `Operation failed after ${maxRetries} attempts: ${lastError!.message}`,
    'RETRY_EXHAUSTED',
    503
  );
};

/**
 * Safe JSON parse with error handling
 */
export const safeJsonParse = <T>(json: string, fallback: T): T => {
  try {
    return JSON.parse(json);
  } catch (error) {
    logError(error as Error, 'JSON Parse');
    return fallback;
  }
};

/**
 * Validate required environment variables
 */
export const validateEnv = (requiredVars: string[]): void => {
  const missing = requiredVars.filter(varName => !import.meta.env[varName]);
  
  if (missing.length > 0) {
    throw new ValidationError(
      `Missing required environment variables: ${missing.join(', ')}`
    );
  }
};

export default {
  AppError,
  ValidationError,
  NotFoundError,
  AuthenticationError,
  FirebaseError,
  NetworkError,
  asyncHandler,
  logError,
  handleFirebaseError,
  formatErrorForUser,
  retryWithBackoff,
  safeJsonParse,
  validateEnv,
};
