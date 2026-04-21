"""Patient Identity — application layer.

Commands, queries, and their handlers. No FastAPI, no SQLAlchemy. The
only permitted imports from outside this package are:

* :mod:`shared_kernel.application` (Command, Query, UnitOfWork, …)
* :mod:`shared_kernel.domain.exceptions`
* :mod:`shared_kernel.types`
* :mod:`patient_identity.domain`
"""
