# Data and Model Files

Canonical model and reference inputs are tracked with targeted Git LFS rules.
Final published reports and figures remain ordinary Git files; generated
outputs, logs, caches, duplicate models, and large test fixtures stay on disk
but are no longer tracked.

Do not add broad LFS rules for entire file types until repository file
ownership has been decided.

See the [approved tracked-artifact inventory](artifact-inventory.md) for the
current size and checksum review, and the
[dependency compatibility matrix](dependency-compatibility.md) for the
package/runtime inventory.
