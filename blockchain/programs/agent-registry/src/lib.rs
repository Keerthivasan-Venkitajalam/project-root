use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token};

declare_id!("AGENTreg1111111111111111111111111111111111");

#[program]
pub mod agent_registry {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let registry = &mut ctx.accounts.registry;
        registry.authority = ctx.accounts.authority.key();
        registry.agent_count = 0;
        Ok(())
    }

    pub fn register_agent(
        ctx: Context<RegisterAgent>, 
        agent_id: String, 
        agent_type: String, 
        capabilities: Vec<String>
    ) -> Result<()> {
        let registry = &mut ctx.accounts.registry;
        let agent = &mut ctx.accounts.agent;
        
        // Set up the agent account
        agent.owner = ctx.accounts.payer.key();
        agent.agent_id = agent_id;
        agent.agent_type = agent_type;
        agent.capabilities = capabilities;
        agent.reputation_score = 0;
        agent.total_contributions = 0;
        agent.created_at = Clock::get()?.unix_timestamp;
        
        // Update registry
        registry.agent_count += 1;
        
        emit!(AgentRegistered {
            agent: agent.key(),
            agent_id: agent.agent_id.clone(),
            owner: agent.owner,
            agent_type: agent.agent_type.clone(),
            capabilities: agent.capabilities.clone(),
        });
        
        Ok(())
    }

    pub fn log_contribution(
        ctx: Context<LogContribution>,
        trace_id: String,
        content_hash: [u8; 32],
        contribution_type: String,
        metadata: String,
    ) -> Result<()> {
        let agent = &mut ctx.accounts.agent;
        let contribution = &mut ctx.accounts.contribution;
        
        // Set up the contribution account
        contribution.agent = agent.key();
        contribution.trace_id = trace_id;
        contribution.content_hash = content_hash;
        contribution.contribution_type = contribution_type;
        contribution.timestamp = Clock::get()?.unix_timestamp;
        contribution.metadata = metadata;
        
        // Update agent statistics
        agent.total_contributions += 1;
        
        emit!(ContributionLogged {
            contribution: contribution.key(),
            agent: agent.key(),
            trace_id: contribution.trace_id.clone(),
            content_hash: contribution.content_hash,
            timestamp: contribution.timestamp,
        });
        
        Ok(())
    }

    pub fn rate_contribution(
        ctx: Context<RateContribution>,
        rating: i64,
        feedback: String,
    ) -> Result<()> {
        let contribution = &mut ctx.accounts.contribution;
        let agent = &mut ctx.accounts.agent;
        
        // Update the contribution with rating
        contribution.rating = Some(rating);
        contribution.feedback = Some(feedback);
        
        // Update agent reputation score (simple weighted average)
        // In a real system, this would be more sophisticated
        agent.reputation_score = if agent.total_contributions <= 1 {
            rating
        } else {
            (agent.reputation_score * (agent.total_contributions - 1) + rating) / agent.total_contributions
        };
        
        emit!(ContributionRated {
            contribution: contribution.key(),
            agent: agent.key(),
            rating,
            feedback: feedback.clone(),
        });
        
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init,
        payer = authority,
        space = Registry::SPACE
    )]
    pub registry: Account<'info, Registry>,
    
    #[account(mut)]
    pub authority: Signer<'info>,
    
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct RegisterAgent<'info> {
    #[account(mut)]
    pub registry: Account<'info, Registry>,
    
    #[account(
        init,
        payer = payer,
        space = Agent::SPACE
    )]
    pub agent: Account<'info, Agent>,
    
    #[account(mut)]
    pub payer: Signer<'info>,
    
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct LogContribution<'info> {
    #[account(mut)]
    pub agent: Account<'info, Agent>,
    
    #[account(
        init,
        payer = payer,
        space = Contribution::SPACE
    )]
    pub contribution: Account<'info, Contribution>,
    
    #[account(mut)]
    pub payer: Signer<'info>,
    
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct RateContribution<'info> {
    #[account(mut)]
    pub contribution: Account<'info, Contribution>,
    
    #[account(mut)]
    pub agent: Account<'info, Agent>,
    
    pub rater: Signer<'info>,
}

#[account]
pub struct Registry {
    pub authority: Pubkey,
    pub agent_count: u64,
}

impl Registry {
    pub const SPACE: usize = 8 + // discriminator
                             32 + // authority: Pubkey
                             8;   // agent_count: u64
}

#[account]
pub struct Agent {
    pub owner: Pubkey,
    pub agent_id: String,      // e.g., "aesthetic-agent"
    pub agent_type: String,    // e.g., "DESIGN", "UX", "COORDINATOR"
    pub capabilities: Vec<String>, // e.g., ["COLOR", "TYPOGRAPHY"]
    pub reputation_score: i64,
    pub total_contributions: i64,
    pub created_at: i64,
}

impl Agent {
    pub const SPACE: usize = 8 + // discriminator
                             32 + // owner: Pubkey
                             4 + 50 + // agent_id: String (max 50 chars)
                             4 + 20 + // agent_type: String (max 20 chars)
                             4 + 10 * (4 + 20) + // capabilities: Vec<String> (max 10 entries of 20 chars)
                             8 + // reputation_score: i64
                             8 + // total_contributions: i64
                             8;  // created_at: i64
}

#[account]
pub struct Contribution {
    pub agent: Pubkey,
    pub trace_id: String,       // unique trace ID for this contribution
    pub content_hash: [u8; 32], // hash of the content for verification
    pub contribution_type: String, // e.g., "DESIGN", "FEEDBACK"
    pub timestamp: i64,
    pub metadata: String,       // Additional JSON metadata
    pub rating: Option<i64>,    // Optional rating (1-10)
    pub feedback: Option<String>, // Optional feedback
}

impl Contribution {
    pub const SPACE: usize = 8 + // discriminator
                             32 + // agent: Pubkey
                             4 + 64 + // trace_id: String (max 64 chars)
                             32 + // content_hash: [u8; 32]
                             4 + 20 + // contribution_type: String (max 20 chars)
                             8 + // timestamp: i64
                             4 + 200 + // metadata: String (max 200 chars)
                             1 + 8 + // rating: Option<i64>
                             1 + 4 + 200; // feedback: Option<String> (max 200 chars)
}

#[event]
pub struct AgentRegistered {
    pub agent: Pubkey,
    pub agent_id: String,
    pub owner: Pubkey,
    pub agent_type: String,
    pub capabilities: Vec<String>,
}

#[event]
pub struct ContributionLogged {
    pub contribution: Pubkey,
    pub agent: Pubkey,
    pub trace_id: String,
    pub content_hash: [u8; 32],
    pub timestamp: i64,
}

#[event]
pub struct ContributionRated {
    pub contribution: Pubkey,
    pub agent: Pubkey,
    pub rating: i64,
    pub feedback: String,
}