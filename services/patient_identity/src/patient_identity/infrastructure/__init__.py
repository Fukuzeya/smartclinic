"""Patient Identity — infrastructure layer.

The only layer permitted to import SQLAlchemy, network libraries, or
other technical adapters. The direction of the dependency graph is
strictly ``api → application → domain ← infrastructure``; the fitness
functions in ``libs/shared_kernel/tests/fitness`` fail the CI build on
violations.
"""
