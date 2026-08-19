# Security policy

## Supported versions

Security fixes are provided for the most recent minor release.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository. Do
not open a public issue containing exploit details or sensitive application
data.

The library treats all browser input as untrusted and validates it again with
Django fields on the server. Consumer-provided schema callables, factories,
serializers, templates, and validators execute as application code and must be
reviewed with the same care as any other Django code.
