# Documentation Linking Standards for ChaseBot

## Purpose
Ensure all project documentation is properly cross-referenced with clear maintenance notes to prevent broken links and outdated references when files change.

## Linking Requirements

### 1. Memory Bank Files Must Link To:
- **Current Implementation Plans**: Link to active development docs
- **Architecture Documents**: Reference current system design
- **Clinerules**: Point to relevant development standards
- **Each Other**: activeContext ↔ progress ↔ techContext

### 2. Implementation Docs Must Link To:
- **Memory Bank**: Reference activeContext and progress
- **Architecture**: Link to system design docs
- **Related Implementations**: Cross-reference related features
- **UAT Documents**: Point to test procedures

### 3. Link Format Template
```markdown
> **📎 Linked Document**: [`docs/example.md`](../docs/example.md)  
> **🔧 Maintenance Note**: If this file is moved/renamed, update:
> - `memory-bank/activeContext.md` (Current Focus section)
> - `memory-bank/progress.md` (Implementation Plan section)
> - Any launch files referencing this implementation
```

## Cross-Reference Matrix

### Memory Bank Dependencies
| File | Links To | Update If Changed |
|------|----------|-------------------|
| activeContext.md | Implementation plans, architecture | All active work references |
| progress.md | Implementation plans, cleanup docs | Task tracking sections |
| techContext.md | Architecture, setup docs | Technical stack references |

### Implementation Dependencies
| File | Links To | Update If Changed |
|------|----------|-------------------|
| d415_implementation_plan.md | Memory bank, architecture | All D415 references |
| architecture.md | Memory bank, implementations | System design sections |
| UAT slices | Implementation plan, progress | Test procedure links |

## Maintenance Patterns

### When Adding New Documentation
1. **Add Forward Links**: Link to related existing docs
2. **Add Backward Links**: Update existing docs to link back
3. **Document Dependencies**: Note what needs updating if moved
4. **Update Memory Bank**: Add to activeContext if current work

### When Removing Documentation
1. **Search for References**: `grep -r "filename" .`
2. **Update All Links**: Remove or redirect references
3. **Archive if Historical**: Move to archive/ with redirect note
4. **Update Memory Bank**: Note removal in progress.md

### When Renaming/Moving Files
1. **Update All References**: Use search/replace across project
2. **Add Redirect Note**: Leave breadcrumb at old location
3. **Update Link Paths**: Adjust relative paths as needed
4. **Test All Links**: Verify no broken references

## Standard Link Blocks

### For Implementation Documents
```markdown
## Related Documentation

> **📎 Memory Bank Context**: [`memory-bank/activeContext.md`](../memory-bank/activeContext.md)  
> **🔧 Maintenance**: Update "Current Focus" section if this implementation changes

> **📎 Progress Tracking**: [`memory-bank/progress.md`](../memory-bank/progress.md)  
> **🔧 Maintenance**: Update implementation checklist when completing slices

> **📎 Architecture**: [`docs/architecture.md`](../docs/architecture.md)  
> **🔧 Maintenance**: Update if this changes system design
```

### For Memory Bank Files
```markdown
## Active Implementation Links

> **📎 Current Work**: [`docs/d415_implementation_plan.md`](../docs/d415_implementation_plan.md)  
> **🔧 Maintenance**: Update this reference when switching to new implementation

> **📎 Clinerules**: [`.clinerules/`](../.clinerules/)  
> **🔧 Maintenance**: These rules govern all development standards
```

## Benefits

1. **No Broken Links**: Clear maintenance notes prevent orphaned references
2. **Easy Navigation**: Developers can trace through related docs
3. **Update Clarity**: Know exactly what needs changing
4. **Context Preservation**: Links maintain project understanding

## Enforcement

- Code reviews check for proper linking in new docs
- Monthly link audit to find broken references
- Automated CI check for common broken link patterns
- Memory bank updates must include link verification
