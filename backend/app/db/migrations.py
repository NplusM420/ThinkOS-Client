"""
Simple version-based database migration system.

Migrations run automatically when the database is unlocked.
Each migration is idempotent (safe to re-run).
"""

from typing import Callable
from sqlalchemy import Connection, text


MigrationFunc = Callable[[Connection], None]

# Migration registry: (version, description, function)
MIGRATIONS: list[tuple[int, str, MigrationFunc]] = []


def migration(version: int, description: str):
    """Decorator to register a migration."""
    def decorator(func: MigrationFunc) -> MigrationFunc:
        MIGRATIONS.append((version, description, func))
        return func
    return decorator


# --- Schema version tracking ---

SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


def get_current_version(conn: Connection) -> int:
    """Get the current schema version, or 0 if no migrations applied."""
    result = conn.execute(text(
        "SELECT MAX(version) FROM schema_version"
    )).scalar()
    return result or 0


def record_migration(conn: Connection, version: int, description: str) -> None:
    """Record that a migration was applied."""
    conn.execute(text(
        "INSERT INTO schema_version (version, description) VALUES (:v, :d)"
    ), {"v": version, "d": description})


# --- Migrations ---

@migration(1, "Create memories table")
def migration_001(conn: Connection) -> None:
    """Create memories table if it doesn't exist."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memories'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE memories (
                id INTEGER PRIMARY KEY,
                type VARCHAR(20) NOT NULL DEFAULT 'web',
                url VARCHAR(2048),
                title VARCHAR(500),
                content TEXT,
                summary TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))


@migration(2, "Add tags and memory_tags tables")
def migration_002(conn: Connection) -> None:
    """Create tags and memory_tags tables."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tags'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE tags (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE
            )
        """))

    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_tags'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE memory_tags (
                memory_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                source VARCHAR(10) NOT NULL DEFAULT 'manual',
                PRIMARY KEY (memory_id, tag_id),
                FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
        """))


@migration(3, "Add embedding column to memories")
def migration_003(conn: Connection) -> None:
    """Add embedding column for vector search."""
    result = conn.execute(text("PRAGMA table_info(memories)")).fetchall()
    columns = [row[1] for row in result]

    if "embedding" not in columns:
        conn.execute(text("ALTER TABLE memories ADD COLUMN embedding BLOB"))


@migration(4, "Add settings table")
def migration_004(conn: Connection) -> None:
    """Create settings table."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='settings'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE settings (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT NOT NULL
            )
        """))


@migration(5, "Add original_title column to memories")
def migration_005(conn: Connection) -> None:
    """Add original_title column for storing original web page titles."""
    result = conn.execute(text("PRAGMA table_info(memories)")).fetchall()
    columns = [row[1] for row in result]

    if "original_title" not in columns:
        conn.execute(text("ALTER TABLE memories ADD COLUMN original_title VARCHAR(500)"))


@migration(6, "Create conversations and messages tables")
def migration_006(conn: Connection) -> None:
    """Create tables for chat history."""
    # Create conversations table
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE conversations (
                id INTEGER PRIMARY KEY,
                title VARCHAR(255) NOT NULL DEFAULT '',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))

    # Create messages table
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY,
                conversation_id INTEGER NOT NULL,
                role VARCHAR(10) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """))


@migration(7, "Create message_sources table for persisting chat sources")
def migration_007(conn: Connection) -> None:
    """Create message_sources table for storing RAG sources per message."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='message_sources'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE message_sources (
                id INTEGER PRIMARY KEY,
                message_id INTEGER NOT NULL,
                memory_id INTEGER NOT NULL,
                relevance_score REAL,
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
                FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE,
                UNIQUE(message_id, memory_id)
            )
        """))
        # Index for efficient lookups
        conn.execute(text("""
            CREATE INDEX idx_message_sources_message_id ON message_sources(message_id)
        """))


def _has_fts5_support(conn: Connection) -> bool:
    """Check if FTS5 module is available in this SQLite build."""
    try:
        conn.execute(text("CREATE VIRTUAL TABLE _fts5_test USING fts5(test)"))
        conn.execute(text("DROP TABLE _fts5_test"))
        return True
    except Exception:
        return False


@migration(8, "Add FTS5 full-text search for memories")
def migration_008(conn: Connection) -> None:
    """Create FTS5 virtual table for hybrid search."""
    # Check if FTS5 is available (not all SQLite builds include it)
    if not _has_fts5_support(conn):
        print("Warning: FTS5 not available in this SQLite build. Skipping FTS migration.")
        print("Full-text search will use fallback LIKE queries instead.")
        return

    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memories_fts'"
    )).fetchone()

    if result:
        return  # Already exists

    # Check if FTS5 module is available (not compiled into all SQLite builds,
    # e.g., rotki-pysqlcipher3 on Windows doesn't include FTS5)
    try:
        conn.execute(text("CREATE VIRTUAL TABLE _fts5_test USING fts5(test)"))
        conn.execute(text("DROP TABLE _fts5_test"))
    except Exception:
        print("WARNING: FTS5 module not available - full-text search will be disabled", flush=True)
        return

    # Create FTS5 virtual table
    conn.execute(text("""
        CREATE VIRTUAL TABLE memories_fts USING fts5(
            title,
            content,
            content='memories',
            content_rowid='id'
        )
    """))

    # Populate with existing data
    conn.execute(text("""
        INSERT INTO memories_fts(rowid, title, content)
        SELECT id, COALESCE(title, ''), COALESCE(content, '')
        FROM memories
    """))

    # Create triggers to keep FTS in sync
    conn.execute(text("""
        CREATE TRIGGER memories_fts_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, title, content)
            VALUES (new.id, COALESCE(new.title, ''), COALESCE(new.content, ''));
        END
    """))

    conn.execute(text("""
        CREATE TRIGGER memories_fts_ad AFTER DELETE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, title, content)
            VALUES ('delete', old.id, COALESCE(old.title, ''), COALESCE(old.content, ''));
        END
    """))

    conn.execute(text("""
        CREATE TRIGGER memories_fts_au AFTER UPDATE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, title, content)
            VALUES ('delete', old.id, COALESCE(old.title, ''), COALESCE(old.content, ''));
            INSERT INTO memories_fts(rowid, title, content)
            VALUES (new.id, COALESCE(new.title, ''), COALESCE(new.content, ''));
        END
    """))


@migration(9, "Add token usage columns to messages")
def migration_009(conn: Connection) -> None:
    """Add token usage tracking to messages."""
    result = conn.execute(text("PRAGMA table_info(messages)")).fetchall()
    columns = [row[1] for row in result]

    if "prompt_tokens" not in columns:
        conn.execute(text("ALTER TABLE messages ADD COLUMN prompt_tokens INTEGER"))
    if "completion_tokens" not in columns:
        conn.execute(text("ALTER TABLE messages ADD COLUMN completion_tokens INTEGER"))
    if "total_tokens" not in columns:
        conn.execute(text("ALTER TABLE messages ADD COLUMN total_tokens INTEGER"))


@migration(10, "Add embedding_model column to memories")
def migration_010(conn: Connection) -> None:
    """Track which embedding model was used for each memory."""
    result = conn.execute(text("PRAGMA table_info(memories)")).fetchall()
    columns = [row[1] for row in result]

    if "embedding_model" not in columns:
        conn.execute(text("ALTER TABLE memories ADD COLUMN embedding_model VARCHAR(100)"))


@migration(11, "Create jobs table for background task tracking")
def migration_011(conn: Connection) -> None:
    """Create jobs table for tracking background tasks like re-embedding."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE jobs (
                id VARCHAR(36) PRIMARY KEY,
                type VARCHAR(50) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                params TEXT,
                result TEXT,
                error TEXT,
                progress INTEGER DEFAULT 0,
                processed INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                total INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_jobs_type_status ON jobs(type, status)"
        ))


@migration(12, "Add pinned column to conversations")
def migration_012(conn: Connection) -> None:
    """Add pinned boolean to conversations for pinning feature."""
    result = conn.execute(text("PRAGMA table_info(conversations)")).fetchall()
    columns = [row[1] for row in result]

    if "pinned" not in columns:
        conn.execute(text("ALTER TABLE conversations ADD COLUMN pinned INTEGER DEFAULT 0"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_conversations_pinned ON conversations(pinned)"))


@migration(13, "Add embedding_summary column to memories")
def migration_013(conn: Connection) -> None:
    """Add embedding_summary for structured semantic search summaries."""
    result = conn.execute(text("PRAGMA table_info(memories)")).fetchall()
    columns = [row[1] for row in result]

    if "embedding_summary" not in columns:
        conn.execute(text("ALTER TABLE memories ADD COLUMN embedding_summary TEXT"))


@migration(14, "Add processing_attempts column to memories")
def migration_014(conn: Connection) -> None:
    """Track failed processing attempts to prevent infinite retry loops."""
    result = conn.execute(text("PRAGMA table_info(memories)")).fetchall()
    columns = [row[1] for row in result]

    if "processing_attempts" not in columns:
        conn.execute(text("ALTER TABLE memories ADD COLUMN processing_attempts INTEGER DEFAULT 0"))


@migration(15, "Create tools table")
def migration_015(conn: Connection) -> None:
    """Create tools table for agent tool definitions."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tools'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE tools (
                id VARCHAR(100) PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description TEXT NOT NULL,
                category VARCHAR(50) NOT NULL,
                parameters_schema TEXT NOT NULL,
                permissions TEXT,
                is_builtin BOOLEAN DEFAULT 0,
                is_enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))


@migration(16, "Create secrets table")
def migration_016(conn: Connection) -> None:
    """Create secrets table for encrypted API keys and credentials."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='secrets'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE secrets (
                name VARCHAR(100) PRIMARY KEY,
                encrypted_value BLOB NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))


@migration(17, "Create agents table")
def migration_017(conn: Connection) -> None:
    """Create agents table for agent definitions."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='agents'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE agents (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                system_prompt TEXT NOT NULL,
                model_provider VARCHAR(50) DEFAULT 'openai',
                model_name VARCHAR(100) DEFAULT 'gpt-4o',
                tools TEXT,
                max_steps INTEGER DEFAULT 10,
                timeout_seconds INTEGER DEFAULT 300,
                is_enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))


@migration(18, "Create agent_runs table")
def migration_018(conn: Connection) -> None:
    """Create agent_runs table for tracking agent executions."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_runs'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE agent_runs (
                id INTEGER PRIMARY KEY,
                agent_id INTEGER NOT NULL,
                input TEXT NOT NULL,
                output TEXT,
                status VARCHAR(20) DEFAULT 'pending',
                error TEXT,
                steps_completed INTEGER DEFAULT 0,
                total_tokens INTEGER,
                duration_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
            )
        """))


@migration(19, "Create agent_run_steps table")
def migration_019(conn: Connection) -> None:
    """Create agent_run_steps table for tracking individual steps in agent runs."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_run_steps'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE agent_run_steps (
                id INTEGER PRIMARY KEY,
                run_id INTEGER NOT NULL,
                step_number INTEGER NOT NULL,
                step_type VARCHAR(20) NOT NULL,
                content TEXT,
                tool_name VARCHAR(100),
                tool_input TEXT,
                tool_output TEXT,
                tokens_used INTEGER,
                duration_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE
            )
        """))


@migration(20, "Create tool_executions table")
def migration_020(conn: Connection) -> None:
    """Create tool_executions table for audit logging of tool usage."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tool_executions'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE tool_executions (
                id INTEGER PRIMARY KEY,
                tool_id VARCHAR(100) NOT NULL,
                agent_run_id INTEGER,
                parameters TEXT,
                result TEXT,
                error TEXT,
                status VARCHAR(20) DEFAULT 'pending',
                duration_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tool_id) REFERENCES tools(id) ON DELETE CASCADE,
                FOREIGN KEY (agent_run_id) REFERENCES agent_runs(id) ON DELETE SET NULL
            )
        """))


@migration(21, "Create workflows table")
def migration_021(conn: Connection) -> None:
    """Create workflows table for workflow definitions."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='workflows'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE workflows (
                id INTEGER PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                description TEXT,
                nodes TEXT,
                edges TEXT,
                variables TEXT,
                status VARCHAR(20) DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))


@migration(22, "Create workflow_runs table")
def migration_022(conn: Connection) -> None:
    """Create workflow_runs table for tracking workflow executions."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='workflow_runs'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE workflow_runs (
                id INTEGER PRIMARY KEY,
                workflow_id INTEGER NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                input TEXT,
                output TEXT,
                error TEXT,
                current_node_id VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
            )
        """))


@migration(23, "Create workflow_run_steps table")
def migration_023(conn: Connection) -> None:
    """Create workflow_run_steps table for tracking individual steps in workflow runs."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='workflow_run_steps'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE workflow_run_steps (
                id INTEGER PRIMARY KEY,
                run_id INTEGER NOT NULL,
                node_id VARCHAR(100) NOT NULL,
                status VARCHAR(20) NOT NULL,
                output TEXT,
                error TEXT,
                duration_ms INTEGER,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES workflow_runs(id) ON DELETE CASCADE
            )
        """))


@migration(24, "Create memory_edges table for knowledge graph")
def migration_024(conn: Connection) -> None:
    """Create memory_edges table for knowledge graph relationships."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_edges'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE memory_edges (
                id INTEGER PRIMARY KEY,
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                relationship_type VARCHAR(100) NOT NULL,
                label VARCHAR(200),
                weight REAL DEFAULT 1.0,
                metadata TEXT,
                source VARCHAR(20) DEFAULT 'auto',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES memories(id) ON DELETE CASCADE,
                FOREIGN KEY (target_id) REFERENCES memories(id) ON DELETE CASCADE,
                UNIQUE(source_id, target_id, relationship_type)
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_memory_edges_source ON memory_edges(source_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_memory_edges_target ON memory_edges(target_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_memory_edges_type ON memory_edges(relationship_type)"
        ))


@migration(25, "Create entities table for knowledge graph nodes")
def migration_025(conn: Connection) -> None:
    """Create entities table for extracted entities from memories."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='entities'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE entities (
                id INTEGER PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                entity_type VARCHAR(50) NOT NULL,
                description TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, entity_type)
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name)"
        ))


@migration(26, "Create memory_entities junction table")
def migration_026(conn: Connection) -> None:
    """Create memory_entities table linking memories to entities."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_entities'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE memory_entities (
                memory_id INTEGER NOT NULL,
                entity_id INTEGER NOT NULL,
                relevance REAL DEFAULT 1.0,
                context TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (memory_id, entity_id),
                FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE,
                FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_memory_entities_memory ON memory_entities(memory_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_memory_entities_entity ON memory_entities(entity_id)"
        ))


@migration(27, "Create inbox_items table")
def migration_027(conn: Connection) -> None:
    """Create inbox_items table for Smart Inbox feature."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='inbox_items'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE inbox_items (
                id INTEGER PRIMARY KEY,
                item_type VARCHAR(50) NOT NULL,
                title VARCHAR(500) NOT NULL,
                content TEXT,
                metadata TEXT,
                priority INTEGER DEFAULT 0,
                is_read BOOLEAN DEFAULT FALSE,
                is_dismissed BOOLEAN DEFAULT FALSE,
                is_actionable BOOLEAN DEFAULT FALSE,
                action_type VARCHAR(50),
                action_data TEXT,
                source_memory_id INTEGER,
                related_memory_ids TEXT,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMP,
                FOREIGN KEY (source_memory_id) REFERENCES memories(id) ON DELETE SET NULL
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_inbox_items_type ON inbox_items(item_type)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_inbox_items_read ON inbox_items(is_read)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_inbox_items_created ON inbox_items(created_at DESC)"
        ))


@migration(28, "Create scheduled_jobs table")
def migration_028(conn: Connection) -> None:
    """Create scheduled_jobs table for APScheduler persistence."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='scheduled_jobs'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            CREATE TABLE scheduled_jobs (
                id VARCHAR(100) PRIMARY KEY,
                job_type VARCHAR(50) NOT NULL,
                name VARCHAR(200) NOT NULL,
                description TEXT,
                schedule_type VARCHAR(20) NOT NULL,
                schedule_value TEXT NOT NULL,
                handler VARCHAR(200) NOT NULL,
                handler_args TEXT,
                is_enabled BOOLEAN DEFAULT TRUE,
                last_run_at TIMESTAMP,
                next_run_at TIMESTAMP,
                run_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                last_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_enabled ON scheduled_jobs(is_enabled)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_next_run ON scheduled_jobs(next_run_at)"
        ))


@migration(29, "Seed pre-built agent templates")
def migration_029(conn: Connection) -> None:
    """Create pre-built agent templates for common use cases."""
    # Check if we already have agents (don't overwrite user data)
    result = conn.execute(text("SELECT COUNT(*) FROM agents")).scalar()
    if result and result > 0:
        return  # Already has agents, skip seeding
    
    # Pre-built agent templates
    agents = [
        {
            "name": "Research Assistant",
            "description": "Deep research and analysis specialist for thorough investigation of topics",
            "system_prompt": """You are a meticulous Research Assistant with expertise in gathering, analyzing, and synthesizing information from multiple sources.

## Your Approach
- **Thorough Investigation**: Explore topics from multiple angles, considering different perspectives and sources
- **Critical Analysis**: Evaluate information quality, identify biases, and distinguish facts from opinions
- **Structured Synthesis**: Organize findings into clear, logical frameworks with proper citations
- **Academic Rigor**: Apply scholarly standards to research methodology and presentation

## Research Process
1. **Clarify Scope**: Understand exactly what the user wants to learn
2. **Gather Sources**: Collect relevant information from the page context and your knowledge
3. **Analyze & Compare**: Cross-reference information, note agreements and contradictions
4. **Synthesize Findings**: Create comprehensive summaries with key insights
5. **Identify Gaps**: Note what's unknown or requires further investigation

## Output Style
- Use clear headings and bullet points for scanability
- Cite sources when referencing specific information
- Distinguish between established facts, expert opinions, and speculation
- Provide confidence levels for conclusions when appropriate
- Suggest follow-up questions or areas for deeper research

Always prioritize accuracy over speed. If information is uncertain or conflicting, say so clearly.""",
        },
        {
            "name": "Code Helper",
            "description": "Expert programming assistant for debugging, explaining, and writing code",
            "system_prompt": """You are an expert Code Helper with deep knowledge across programming languages, frameworks, and software engineering best practices.

## Your Expertise
- **Languages**: Python, JavaScript/TypeScript, Rust, Go, Java, C++, and more
- **Frameworks**: React, Vue, Node.js, FastAPI, Django, and modern web stacks
- **Practices**: Clean code, design patterns, testing, performance optimization, security

## How You Help
1. **Explain Code**: Break down complex code into understandable pieces, explaining the "why" not just the "what"
2. **Debug Issues**: Systematically identify bugs, explain root causes, and provide fixes
3. **Write Code**: Generate clean, well-documented, production-ready code
4. **Review & Improve**: Suggest optimizations, better patterns, and potential issues
5. **Teach Concepts**: Explain programming concepts with clear examples

## Code Style
- Write idiomatic code following language conventions
- Include helpful comments for complex logic
- Consider edge cases and error handling
- Prioritize readability and maintainability
- Suggest tests when appropriate

## Response Format
- Use code blocks with proper syntax highlighting
- Explain changes and reasoning clearly
- Provide complete, runnable examples when possible
- Note any assumptions or dependencies

When reviewing code from the current page, be specific about line numbers and exact issues.""",
        },
        {
            "name": "Creative Writer",
            "description": "Imaginative writing partner for stories, content, and creative projects",
            "system_prompt": """You are a Creative Writer with a gift for crafting compelling narratives, engaging content, and imaginative prose.

## Your Creative Strengths
- **Storytelling**: Craft narratives with compelling characters, vivid settings, and engaging plots
- **Voice & Tone**: Adapt writing style to match any genre, audience, or brand voice
- **Content Creation**: Blog posts, marketing copy, social media, scripts, and more
- **Editing & Polish**: Refine rough drafts into polished, publication-ready pieces

## Creative Process
1. **Understand the Vision**: Clarify the purpose, audience, tone, and constraints
2. **Brainstorm Ideas**: Generate multiple creative directions and concepts
3. **Draft & Iterate**: Create initial versions, then refine based on feedback
4. **Polish & Perfect**: Fine-tune word choice, rhythm, and impact

## Writing Principles
- Show, don't tell - use vivid details and sensory language
- Every word should earn its place - be concise yet evocative
- Vary sentence structure for rhythm and flow
- Create emotional resonance with authentic human experiences
- Surprise and delight with unexpected turns of phrase

## Collaboration Style
- Offer multiple options when brainstorming
- Explain creative choices when asked
- Build on the user's ideas rather than replacing them
- Respect the user's voice and vision

I'm here to amplify your creativity, not replace it. Let's create something amazing together!""",
        },
        {
            "name": "Study Buddy",
            "description": "Patient tutor that explains concepts clearly and helps with learning",
            "system_prompt": """You are a patient, encouraging Study Buddy dedicated to helping users learn and understand new concepts.

## Teaching Philosophy
- **Meet Learners Where They Are**: Adapt explanations to the user's current understanding
- **Build Understanding**: Focus on "why" and "how," not just "what"
- **Encourage Curiosity**: Foster a love of learning through engaging explanations
- **Celebrate Progress**: Acknowledge effort and growth, not just correct answers

## How You Teach
1. **Assess Understanding**: Ask clarifying questions to gauge current knowledge
2. **Explain Clearly**: Use simple language, analogies, and real-world examples
3. **Break It Down**: Divide complex topics into digestible chunks
4. **Check Comprehension**: Ask questions to verify understanding
5. **Reinforce Learning**: Summarize key points and suggest practice

## Explanation Techniques
- Use analogies to connect new concepts to familiar ideas
- Provide concrete examples before abstract principles
- Create mental models and frameworks for organizing knowledge
- Use visual descriptions when helpful (diagrams, flowcharts)
- Relate topics to practical applications

## Encouragement Style
- Normalize struggle as part of learning
- Praise specific efforts and improvements
- Reframe mistakes as learning opportunities
- Build confidence through incremental challenges

Remember: There are no stupid questions. Every question is an opportunity to learn!""",
        },
        {
            "name": "Summarizer",
            "description": "Concise summarization expert that distills content to key points",
            "system_prompt": """You are a Summarization Expert who excels at distilling complex content into clear, actionable summaries.

## Your Specialty
Transform lengthy articles, documents, and discussions into concise, well-organized summaries that capture the essential information.

## Summarization Approach
1. **Identify Core Message**: What is the main point or thesis?
2. **Extract Key Points**: What are the most important supporting ideas?
3. **Note Critical Details**: What specific facts, figures, or examples matter?
4. **Capture Conclusions**: What are the takeaways or action items?

## Output Formats

**Quick Summary** (1-2 sentences):
- The absolute essence in minimal words

**Key Points** (bullet list):
- Main ideas in scannable format
- Typically 3-7 points

**Executive Summary** (1-2 paragraphs):
- Comprehensive overview for decision-makers
- Includes context, findings, and implications

**Structured Summary**:
- Background/Context
- Main Findings
- Key Details
- Conclusions/Recommendations

## Principles
- Preserve meaning while reducing length
- Maintain the author's intent and tone
- Prioritize actionable information
- Use clear, direct language
- Indicate when important nuance is lost in summarization

When summarizing page content, I'll automatically choose the most appropriate format based on the content type and length. Just ask me to summarize!""",
        },
        {
            "name": "Devil's Advocate",
            "description": "Critical thinker that challenges assumptions and explores counterarguments",
            "system_prompt": """You are a Devil's Advocate - a critical thinking partner who helps users stress-test their ideas by exploring counterarguments and alternative perspectives.

## Your Role
Challenge assumptions, identify weaknesses, and explore opposing viewpoints - not to be contrarian, but to strengthen thinking and decision-making.

## How You Challenge
1. **Question Assumptions**: What unstated beliefs underlie this position?
2. **Explore Alternatives**: What other explanations or approaches exist?
3. **Identify Weaknesses**: Where are the logical gaps or vulnerabilities?
4. **Consider Consequences**: What could go wrong? What's being overlooked?
5. **Steel-man Opposition**: Present the strongest version of opposing views

## Critical Thinking Tools
- **Socratic Questioning**: Guide discovery through probing questions
- **Logical Analysis**: Identify fallacies, biases, and reasoning errors
- **Perspective Shifting**: View issues from different stakeholder viewpoints
- **Scenario Planning**: Explore best-case, worst-case, and likely outcomes
- **Pre-mortem Analysis**: Imagine failure and work backward to causes

## Engagement Style
- Respectful but direct - challenge ideas, not people
- Acknowledge valid points before presenting counterarguments
- Explain the reasoning behind challenges
- Offer constructive paths forward, not just criticism
- Know when to stop - the goal is better thinking, not endless debate

## Important Note
I challenge to strengthen, not to discourage. A well-tested idea is a stronger idea. Let's pressure-test your thinking!""",
        },
    ]
    
    for agent in agents:
        conn.execute(text("""
            INSERT INTO agents (name, description, system_prompt, is_enabled)
            VALUES (:name, :description, :system_prompt, 1)
        """), agent)


@migration(30, "Add enhanced agent orchestration tables")
def migration_030(conn: Connection) -> None:
    """Create tables for enhanced agent orchestration with planning and evaluation."""
    
    # Add new columns to agent_run_steps for enhanced orchestration
    result = conn.execute(text("PRAGMA table_info(agent_run_steps)")).fetchall()
    columns = [row[1] for row in result]
    
    if "plan_step_number" not in columns:
        conn.execute(text("ALTER TABLE agent_run_steps ADD COLUMN plan_step_number INTEGER"))
    if "thinking_block" not in columns:
        conn.execute(text("ALTER TABLE agent_run_steps ADD COLUMN thinking_block TEXT"))
    
    # Create agent_run_plans table
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_run_plans'"
    )).fetchone()
    
    if not result:
        conn.execute(text("""
            CREATE TABLE agent_run_plans (
                id INTEGER PRIMARY KEY,
                run_id INTEGER NOT NULL UNIQUE,
                goal TEXT NOT NULL,
                approach TEXT NOT NULL,
                current_step INTEGER DEFAULT 0,
                total_steps INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_agent_run_plans_run ON agent_run_plans(run_id)"
        ))
    
    # Create agent_run_plan_steps table
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_run_plan_steps'"
    )).fetchone()
    
    if not result:
        conn.execute(text("""
            CREATE TABLE agent_run_plan_steps (
                id INTEGER PRIMARY KEY,
                plan_id INTEGER NOT NULL,
                step_number INTEGER NOT NULL,
                description TEXT NOT NULL,
                reasoning TEXT,
                expected_tools TEXT,
                success_criteria TEXT,
                status VARCHAR(20) DEFAULT 'pending',
                result TEXT,
                error TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (plan_id) REFERENCES agent_run_plans(id) ON DELETE CASCADE
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_agent_run_plan_steps_plan ON agent_run_plan_steps(plan_id)"
        ))
    
    # Create agent_run_evaluations table
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_run_evaluations'"
    )).fetchone()
    
    if not result:
        conn.execute(text("""
            CREATE TABLE agent_run_evaluations (
                id INTEGER PRIMARY KEY,
                run_id INTEGER NOT NULL,
                plan_step_number INTEGER,
                step_successful BOOLEAN NOT NULL,
                goal_progress REAL NOT NULL,
                reasoning TEXT NOT NULL,
                should_continue BOOLEAN DEFAULT TRUE,
                needs_replanning BOOLEAN DEFAULT FALSE,
                suggested_changes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_agent_run_evaluations_run ON agent_run_evaluations(run_id)"
        ))


@migration(31, "Add video clips tables for Clippy integration")
def migration_31_video_clips(conn: Connection) -> None:
    """Add tables for storing video clips from Clippy."""
    
    # Video clips table
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS video_clips (
            id INTEGER PRIMARY KEY,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            source_url TEXT NOT NULL,
            source_title VARCHAR(500),
            start_time REAL,
            end_time REAL,
            duration REAL,
            thumbnail_url TEXT,
            download_url TEXT,
            preview_url TEXT,
            aspect_ratio VARCHAR(20),
            platform_recommendation VARCHAR(50),
            captions TEXT,
            prompt TEXT,
            clippy_job_id VARCHAR(100),
            clippy_clip_id VARCHAR(100),
            is_favorite BOOLEAN DEFAULT FALSE,
            is_archived BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    # Video clip tags junction table
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS video_clip_tags (
            clip_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (clip_id, tag_id),
            FOREIGN KEY (clip_id) REFERENCES video_clips(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        )
    """))
    
    # Indexes for efficient querying
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_video_clips_source ON video_clips(source_url)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_video_clips_created ON video_clips(created_at DESC)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_video_clips_favorite ON video_clips(is_favorite)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_video_clips_platform ON video_clips(platform_recommendation)"
    ))


# --- Migration runner ---

def run_migrations(conn: Connection) -> list[tuple[int, str]]:
    """
    Run all pending migrations.

    Returns list of (version, description) for migrations that were applied.
    """
    # Ensure schema_version table exists
    conn.execute(text(SCHEMA_VERSION_TABLE))
    conn.commit()

    current_version = get_current_version(conn)
    applied = []

    # Sort migrations by version
    sorted_migrations = sorted(MIGRATIONS, key=lambda m: m[0])

    for version, description, func in sorted_migrations:
        if version > current_version:
            func(conn)
            record_migration(conn, version, description)
            conn.commit()
            applied.append((version, description))

    return applied
