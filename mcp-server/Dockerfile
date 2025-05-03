FROM alpine:latest as zig-builder

# Install dependencies
RUN apk add --no-cache curl tar xz git

# Install Zig
ARG ZIG_VERSION=0.11.0
RUN curl -L https://ziglang.org/download/${ZIG_VERSION}/zig-linux-x86_64-${ZIG_VERSION}.tar.xz -o zig.tar.xz \
    && tar -xf zig.tar.xz \
    && mv zig-linux-x86_64-${ZIG_VERSION} /usr/local/zig \
    && rm zig.tar.xz

# Set PATH
ENV PATH="/usr/local/zig:${PATH}"

# Create app directory
WORKDIR /app

# Copy source files
COPY . .

# Build the application
RUN zig build -Drelease-safe

# Final stage
FROM alpine:latest

WORKDIR /app

# Copy the binary from the builder stage
COPY --from=zig-builder /app/zig-out/bin/mcp-server .

# Expose MCP server port
EXPOSE 8080

# Set entry point
ENTRYPOINT ["./mcp-server"]