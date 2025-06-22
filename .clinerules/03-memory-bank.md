# Cline Memory Bank Integration

## Memory Bank System
ChaseBot uses a comprehensive Memory Bank system located in `/memory-bank/` to maintain context across sessions. This system is critical for project continuity and effective development.

## Core Memory Bank Files

### Foundation Files (Read First)
1. **`memory-bank/projectbrief.md`** - Project overview and core goals
2. **`memory-bank/productContext.md`** - Why the project exists and how it should work
3. **`memory-bank/techContext.md`** - Technologies, constraints, and development environment

### Architecture & Implementation
4. **`memory-bank/systemPatterns.md`** - System architecture and design patterns
5. **`memory-bank/activeContext.md`** - Current work focus and recent changes
6. **`memory-bank/progress.md`** - What works, what's left to build, current status

## Memory Bank Usage Rules

### Session Initialization
- **ALWAYS read ALL memory bank files** at the start of any task
- Use the command: "Following memory bank context from previous sessions"
- Confirm understanding of current project state before proceeding
- Reference specific insights from memory bank files in responses

### Context Confirmation
When starting work, confirm:
- Current project phase and priorities (from `activeContext.md`)
- Technical constraints and decisions (from `techContext.md` and `systemPatterns.md`)
- Recent changes and next steps (from `activeContext.md`)
- Overall project status (from `progress.md`)

### Memory Bank Updates
Update memory bank files when:
- Implementing significant changes or completing milestones
- Discovering new technical patterns or architectural decisions
- User requests "update memory bank"
- Context needs clarification for future sessions

### Update Priority Order
1. **`activeContext.md`** - Most frequently updated (current work and decisions)
2. **`progress.md`** - Track completed work and current status
3. **`systemPatterns.md`** - Document new architectural patterns
4. **`techContext.md`** - Update technical constraints or environment changes

## Integration with ChaseBot Development

### ROS Development Context
- Memory bank captures ROS migration strategy and current phase
- Preserves valuable Webots foundation work and insights
- Maintains technical decisions about Navigation Stack integration
- Documents hardware abstraction patterns and safety requirements

### Professional Development Practices
- Memory bank ensures consistency with documented standards
- Preserves architectural decisions and their rationale
- Maintains development workflow and testing patterns
- Documents lessons learned and proven approaches

## Context Preservation Commands

### Starting Work
- "Read memory bank and continue from previous session"
- "Following memory bank context and current project status"
- "Reviewing memory bank files for project continuation"

### During Development
- "Update memory bank with current progress"
- "Document this decision in memory bank"
- "Preserve this insight for future sessions"

### Session Completion
- "Update memory bank before ending session"
- "Document current state for next session"
- "Preserve context and next steps"

## Critical Success Factors
1. **Consistency**: Always read memory bank files before starting work
2. **Completeness**: Update memory bank with significant changes
3. **Clarity**: Write memory bank updates for future context understanding
4. **Continuity**: Ensure smooth transition between sessions

The Memory Bank is Cline's only link to previous work. Project effectiveness depends entirely on maintaining clear, accurate memory bank documentation.
