# ChaseBot Cline Rules

This directory contains Cline rules that provide system-level guidance for ChaseBot development. These rules ensure consistent, professional robotics development practices across all sessions.

## Rule Files

### 01-chasebot-core.md
Core project principles and development workflow:
- ROS-first development approach
- Documentation-driven development
- Hardware abstraction requirements
- Professional standards and naming conventions

### 02-ros-standards.md
ROS-specific development standards:
- Package organization and naming
- Topic and service conventions
- Parameter organization patterns
- Launch file structure
- Error handling and testing standards

### 03-memory-bank.md
Memory Bank integration instructions:
- How to use the memory bank system
- File reading and updating procedures
- Context preservation commands
- Session continuity best practices

### README.md (this file)
Overview and usage instructions for the rules system.

## How to Use

### For New Sessions
At the start of any ChaseBot development session, Cline will automatically read all `.md` files in this directory. The rules provide:

1. **Project Context**: Understanding of ChaseBot's ROS-based architecture
2. **Development Standards**: Consistent coding and documentation practices
3. **Memory Bank Integration**: Proper context preservation across sessions
4. **Technical Guidelines**: ROS standards and professional practices

### Rule Activation
- **Automatic**: All `.md` files in `.clinerules/` are automatically processed
- **Sequential**: Files are processed in order (01-, 02-, 03-, etc.)
- **Comprehensive**: Rules are combined into unified guidance

### Updating Rules
To modify project standards:
1. Edit the appropriate rule file
2. Commit changes to version control
3. Rules take effect in next Cline session

## Integration with Memory Bank

The rules work together with the `/memory-bank/` system:
- **Rules**: Provide consistent development standards
- **Memory Bank**: Preserves project-specific context and decisions
- **Together**: Enable professional, continuous development workflow

## Benefits

1. **Consistency**: Same development practices across all sessions
2. **Quality**: Professional robotics development standards
3. **Efficiency**: Clear guidelines reduce decision overhead
4. **Continuity**: Seamless transitions between sessions
5. **Collaboration**: Team members follow same standards

## File Structure
```
.clinerules/
├── README.md              # This overview file
├── 01-chasebot-core.md    # Core project principles
├── 02-ros-standards.md    # ROS development standards
└── 03-memory-bank.md      # Memory bank integration
```

These rules ensure ChaseBot development maintains professional standards while preserving the flexibility to adapt and improve over time.
