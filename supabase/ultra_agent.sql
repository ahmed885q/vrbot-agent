-- Ultra Agent tables for VRBOT
-- Run in Supabase SQL editor

CREATE TABLE IF NOT EXISTS ultra_agent_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farm_name TEXT NOT NULL,
    agent_used TEXT NOT NULL,
    action TEXT,
    result TEXT,
    screen_state JSONB DEFAULT '{}',
    duration_ms INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ultra_logs_farm ON ultra_agent_logs(farm_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ultra_logs_agent ON ultra_agent_logs(agent_used);

CREATE TABLE IF NOT EXISTS ultra_agent_config (
    farm_name TEXT PRIMARY KEY,
    enabled BOOLEAN DEFAULT false,
    priority_agents TEXT[] DEFAULT ARRAY['gather','daily','tribe'],
    auto_defense BOOLEAN DEFAULT true,
    learning_mode BOOLEAN DEFAULT true,
    max_cycles_per_hour INTEGER DEFAULT 10,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
