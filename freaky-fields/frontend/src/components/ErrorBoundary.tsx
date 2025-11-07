import React from 'react';
import { Box, Text } from '@chakra-ui/react';

interface ErrorBoundaryState { hasError: boolean; error?: Error }

export class ErrorBoundary extends React.Component<React.PropsWithChildren, ErrorBoundaryState> {
  constructor(props: React.PropsWithChildren) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary] Render error:', error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <Box p={4} bg="red.50" border="1px solid" borderColor="red.200" borderRadius="md">
          <Text fontSize="sm" color="red.600" fontWeight="semibold">Component failed to render.</Text>
          {this.state.error && (
            <Text fontSize="xs" mt={2} color="red.500">{this.state.error.message}</Text>
          )}
        </Box>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
