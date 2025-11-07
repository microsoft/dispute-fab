import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { Box, Flex, Heading, Container } from '@chakra-ui/react';
import './App.css';
import Dashboard from './pages/Dashboard.tsx';
import ClaimDetail from './pages/ClaimDetail.tsx';
import UpdateClaimData from './pages/UpdateClaimData.tsx';
import IngestionAnalysis from './pages/IngestionAnalysis.tsx';
import ErrorBoundary from './components/ErrorBoundary';

const NAV_LINKS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/update', label: 'Update Claim Data' },
  { to: '/analysis', label: 'Ingestion Analysis' },
];

function App() {
  return (
    <BrowserRouter>
      <Box minH="100vh" bg="gray.100" fontFamily="'Inter', 'Segoe UI', sans-serif">
        {/* Navigation */}
        <Box bg="white" borderBottom="2px" borderColor="gray.200" py={4} px={6} boxShadow="sm">
          <Container maxW="container.xl">
            <Flex align="center" justify="space-between">
              <Heading size="xl" color="gray.800" fontWeight="bold">SeeHealth Claims Triage Dashboard</Heading>
              <Flex as="nav" gap={2}>
                {NAV_LINKS.map(({ to, label, end }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={Boolean(end)}
                    className={({ isActive }) =>
                      isActive ? 'nav-link nav-link-active' : 'nav-link'
                    }
                  >
                    {label}
                  </NavLink>
                ))}
              </Flex>
            </Flex>
          </Container>
        </Box>

        {/* Main Content */}
        <Container maxW="container.xl" py={8}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/claim/:claimId" element={<ClaimDetail />} />
            <Route path="/update" element={<UpdateClaimData />} />
            <Route path="/analysis" element={<ErrorBoundary><IngestionAnalysis /></ErrorBoundary>} />
          </Routes>
        </Container>
      </Box>
    </BrowserRouter>
  );
}

export default App;
