const std = @import("std");
const net = std.net;
const mem = std.mem;
const Allocator = std.mem.Allocator;
const json = std.json;

// MCP Protocol Message Types
const MessageType = enum {
    REGISTER,    // Agent registration
    TASK,        // New task assignment
    RESPONSE,    // Agent response
    FEEDBACK,    // Feedback on a response
    QUERY,       // Agent querying another agent
    A2A,         // Direct agent-to-agent communication
};

// MCP Message Structure
const MCPMessage = struct {
    type: MessageType,
    sender: []const u8,
    recipient: []const u8,
    content: []const u8,
    timestamp: i64,
    trace_id: []const u8,
    
    // Optional fields
    parent_id: ?[]const u8 = null,
    metadata: ?[]const u8 = null,
};

// Agent connection state
const AgentConnection = struct {
    id: []const u8,
    stream: net.Stream,
    capabilities: []const []const u8,
    allocator: *Allocator,
};

// MCP Server
pub const MCPServer = struct {
    allocator: *Allocator,
    port: u16,
    agents: std.StringHashMap(AgentConnection),
    
    pub fn init(allocator: *Allocator, port: u16) !MCPServer {
        return MCPServer{
            .allocator = allocator,
            .port = port,
            .agents = std.StringHashMap(AgentConnection).init(allocator),
        };
    }
    
    pub fn deinit(self: *MCPServer) void {
        var it = self.agents.iterator();
        while (it.next()) |entry| {
            entry.value_ptr.stream.close();
            self.allocator.free(entry.value_ptr.id);
        }
        self.agents.deinit();
    }
    
    pub fn start(self: *MCPServer) !void {
        const address = net.Address.parseIp("0.0.0.0", self.port) catch |err| {
            std.debug.print("Failed to parse address: {}\n", .{err});
            return err;
        };
        
        var server = net.StreamServer.init(.{});
        defer server.deinit();
        
        try server.listen(address);
        std.debug.print("MCP Server listening on port {}\n", .{self.port});
        
        while (true) {
            const connection = try server.accept();
            const conn_thread = try std.Thread.spawn(.{}, handleConnection, .{self, connection.stream});
            conn_thread.detach();
        }
    }
    
    fn handleConnection(self: *MCPServer, stream: net.Stream) !void {
        defer stream.close();
        
        var buf: [4096]u8 = undefined;
        
        // First message should be a REGISTER message
        const bytes_read = try stream.read(&buf);
        if (bytes_read == 0) return;
        
        const msg = try json.parse(MCPMessage, &json.TokenStream.init(buf[0..bytes_read]), .{
            .allocator = self.allocator,
        });
        
        if (msg.type != .REGISTER) {
            std.debug.print("First message must be REGISTER, got {}\n", .{msg.type});
            return;
        }
        
        // Register the agent
        const agent_id = try self.allocator.dupe(u8, msg.sender);
        const caps = try json.parse([][]const u8, &json.TokenStream.init(msg.content), .{
            .allocator = self.allocator,
        });
        
        try self.agents.put(agent_id, .{
            .id = agent_id,
            .stream = stream,
            .capabilities = caps,
            .allocator = self.allocator,
        });
        
        std.debug.print("Agent registered: {s}\n", .{agent_id});
        
        // Main message handling loop
        while (true) {
            const read_bytes = try stream.read(&buf);
            if (read_bytes == 0) break;
            
            const message = try json.parse(MCPMessage, &json.TokenStream.init(buf[0..read_bytes]), .{
                .allocator = self.allocator,
            });
            
            try self.routeMessage(message);
        }
        
        // Clean up when agent disconnects
        _ = self.agents.remove(agent_id);
        std.debug.print("Agent disconnected: {s}\n", .{agent_id});
    }
    
    fn routeMessage(self: *MCPServer, message: MCPMessage) !void {
        // If it's an A2A message or has a specific recipient
        if (message.type == .A2A or message.recipient.len > 0) {
            const recipient = self.agents.get(message.recipient) orelse {
                std.debug.print("Unknown recipient: {s}\n", .{message.recipient});
                return;
            };
            
            // Serialize and forward the message
            const json_msg = try json.stringify(message, .{}, recipient.allocator);
            _ = try recipient.stream.write(json_msg);
            recipient.allocator.free(json_msg);
            return;
        }
        
        // Broadcast to all agents with matching capabilities
        // (Implementation depends on message metadata and content)
    }
};

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    
    var server = try MCPServer.init(&gpa.allocator, 8080);
    defer server.deinit();
    
    try server.start();
}