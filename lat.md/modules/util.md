# Module: src/util/

Cross-cutting utilities.

| File | Role |
|------|------|
| [Logger.cpp](../../src/util/Logger.cpp) | leveled logging |
| [Timer.cpp](../../src/util/Timer.cpp) | scoped timing |
| [SpatialHash2D.cpp](../../src/util/SpatialHash2D.cpp) | 2D spatial hash for closest-point queries |
| [Validator.cpp](../../src/util/Validator.cpp) | shared validation primitives |

`SpatialHash2D` is used by [ClosedLoop.cpp](../../src/assembly/ClosedLoop.cpp) for the winding-number
signed-distance computation.
