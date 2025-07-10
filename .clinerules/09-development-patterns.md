# Development Patterns for ChaseBot

## Documentation Pattern

### Every Change Needs:

1. **FILE_REGISTRY.yaml Update**
   - Status, version, test results
   - Known issues
   - Working status

2. **Test Script**
   - Automated verification
   - Clear success/failure criteria

3. **Documentation Update**
   - What changed
   - Why it changed
   - How to test it

## Debugging Pattern

### When Something Doesn't Work:

1. **Check Dependencies First**
   ```bash
   # Example: Vision inference needs
   pip list | grep onnxruntime
   pip list | grep numba
   ```

2. **Verify Topics**
   ```bash
   ros2 topic list
   ros2 topic hz /topic_name
   ros2 topic echo /topic_name --once
   ```

3. **Check Node Status**
   ```bash
   ros2 node list
   ros2 node info /node_name
   ```

4. **Look at Logs**
   - Add debug logging to understand flow
   - Check for error messages
   - Verify data formats

## Communication Pattern

### Clear Status Reporting

✅ **WORKING**: "YOLO detector successfully detects balls at (0.499, 0.547) with 50.5% confidence"
❌ **VAGUE**: "YOLO seems to work"

✅ **NOT WORKING**: "Vision inference publishes empty MarkerArray on /mono3d/bbox, no detections"
❌ **VAGUE**: "Vision inference has issues"

✅ **PARTIAL**: "Node runs without crashes but doesn't detect golf balls (model not trained on them)"
❌ **VAGUE**: "Kind of working"

### Status Categories

1. **VERIFIED WORKING**: Tested and confirmed operational with specific output
2. **PARTIAL**: Some functionality works, specific issues documented
3. **NOT WORKING**: Specific failure mode documented
4. **EXPERIMENTAL**: Under development, not fully tested
5. **DEPRECATED**: Replaced by newer version, document replacement

### Documentation Requirements

- Always include specific test commands
- Document exact output/behavior observed
- Include version numbers and timestamps
- Reference related files and dependencies

## Integration with Other Standards

- Follow file versioning (see 05-file-versioning.md)
- Use testing patterns (see 07-testing-execution.md)
- Update documentation structure (see 08-documentation-structure.md)
- Maintain memory bank (see 03-memory-bank.md)
