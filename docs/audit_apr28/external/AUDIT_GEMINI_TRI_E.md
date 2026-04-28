YOLO mode is enabled. All tool calls will be automatically approved.
YOLO mode is enabled. All tool calls will be automatically approved.
Attempt 1 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 14:57:23 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=6249',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '257594b493d905e',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
Attempt 2 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 14:57:34 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=6804',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '712c6e11c1e441f7',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
Attempt 1 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 14:58:15 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=7500',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': 'fa66004d6a2ee3c7',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
Attempt 1 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 14:58:33 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=5810',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '32ea487b6b3bc489',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
Attempt 1 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 14:58:48 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=5849',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '1b928ea60fb2aa0d',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
Attempt 1 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 14:59:06 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=395',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': 'eb5bd82e8735aa30',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
Attempt 2 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 14:59:16 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=5898',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '169e45761c67e96',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
Attempt 3 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 14:59:26 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=340',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '7c86935bea324549',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
Attempt 4 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 14:59:54 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=6098',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': 'd310cf18c5407ffd',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
Attempt 5 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 15:00:31 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=6576',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '31e1434d5b9fdc6',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
Attempt 1 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 15:01:13 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=6740',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '706d2ead710c4e0e',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
Attempt 2 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 15:01:25 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=7194',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': 'c3abfcf866fc95e1',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
Attempt 3 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 15:01:42 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=6341',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '202361d4e1f90d1c',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
Attempt 4 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 15:02:08 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=7212',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': 'f9461a4df69365a7',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
Attempt 5 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 15:02:48 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=7038',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '2050b1181bede970',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
Attempt 1 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 15:03:22 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=6105',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '876b4931da27ef2b',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
Attempt 1 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 15:04:52 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=7106',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '2182d94639796ca6',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
Attempt 1 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 15:05:17 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=7714',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '51a8e954b31bae7d',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
Attempt 1 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 15:05:44 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=6138',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '2709337d8711db38',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
Attempt 2 failed with status 429. Retrying with backoff... _GaxiosError: [{
  "error": {
    "code": 429,
    "message": "No capacity available for model gemini-3.1-pro-preview on the server",
    "errors": [
      {
        "message": "No capacity available for model gemini-3.1-pro-preview on the server",
        "domain": "global",
        "reason": "rateLimitExceeded"
      }
    ],
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "MODEL_CAPACITY_EXHAUSTED",
        "domain": "cloudcode-pa.googleapis.com",
        "metadata": {
          "model": "gemini-3.1-pro-preview"
        }
      }
    ]
  }
}
]
    at Gaxios._request (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:8578:19)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async _OAuth2Client.requestAsync (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:10541:16)
    at async CodeAssistServer.requestStreamingPost (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277484:17)
    at async CodeAssistServer.generateContentStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:277284:23)
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:278125:19
    at async file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:255118:23
    at async retryWithBackoff (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:275082:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310999:28)
    at async GeminiChat.streamWithRetries (file:///opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/chunk-IWSCP2GY.js:310837:29) {
  config: {
    url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
    method: 'POST',
    params: { alt: 'sse' },
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'GeminiCLI/0.38.2/gemini-3.1-pro-preview (darwin; arm64; terminal) google-api-nodejs-client/9.15.1',
      Authorization: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      'x-goog-api-client': 'gl-node/25.6.1'
    },
    responseType: 'stream',
    body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
    signal: AbortSignal { aborted: false },
    retry: false,
    paramsSerializer: [Function: paramsSerializer],
    validateStatus: [Function: validateStatus],
    errorRedactor: [Function: defaultErrorRedactor]
  },
  response: {
    config: {
      url: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse',
      method: 'POST',
      params: [Object],
      headers: [Object],
      responseType: 'stream',
      body: '<<REDACTED> - See `errorRedactor` option in `gaxios` for configuration>.',
      signal: [AbortSignal],
      retry: false,
      paramsSerializer: [Function: paramsSerializer],
      validateStatus: [Function: validateStatus],
      errorRedactor: [Function: defaultErrorRedactor]
    },
    data: '[{\n' +
      '  "error": {\n' +
      '    "code": 429,\n' +
      '    "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '    "errors": [\n' +
      '      {\n' +
      '        "message": "No capacity available for model gemini-3.1-pro-preview on the server",\n' +
      '        "domain": "global",\n' +
      '        "reason": "rateLimitExceeded"\n' +
      '      }\n' +
      '    ],\n' +
      '    "status": "RESOURCE_EXHAUSTED",\n' +
      '    "details": [\n' +
      '      {\n' +
      '        "@type": "type.googleapis.com/google.rpc.ErrorInfo",\n' +
      '        "reason": "MODEL_CAPACITY_EXHAUSTED",\n' +
      '        "domain": "cloudcode-pa.googleapis.com",\n' +
      '        "metadata": {\n' +
      '          "model": "gemini-3.1-pro-preview"\n' +
      '        }\n' +
      '      }\n' +
      '    ]\n' +
      '  }\n' +
      '}\n' +
      ']',
    headers: {
      'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000',
      'content-length': '630',
      'content-type': 'application/json; charset=UTF-8',
      date: 'Tue, 28 Apr 2026 15:05:56 GMT',
      server: 'ESF',
      'server-timing': 'gfet4t7; dur=7944',
      vary: 'Origin, X-Origin, Referer',
      'x-cloudaicompanion-trace-id': '76551349cc7c1e3',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'SAMEORIGIN',
      'x-xss-protection': '0'
    },
    status: 429,
    statusText: 'Too Many Requests',
    request: {
      responseURL: 'https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse'
    }
  },
  error: undefined,
  status: 429,
  Symbol(gaxios-gaxios-error): '6.7.1'
}
SCORE: 90/100. VERDICT: Round D actionable code findings are successfully shipped, but `InProcessEventBus` technical debt is missing from documentation.

- **Missing Technical Debt:** `docs/SCALING.md` documents "In-Memory Notification Store Migration" and "RBAC scope hardening", but completely omits the `InProcessEventBus full pub/sub` legacy architecture.
- **Minor Naming Discrepancy:** The background tasks in `backend/routers/risks.py` and `backend/services/vapt_vendor_service.py` are correctly attached to a done-callback, but the function is named `_log_enrich_failure` rather than `_log_task_result` as specified.
