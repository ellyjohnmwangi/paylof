import { render, screen } from '@testing-library/react';
import App from './App';

test('renders the PAYLOFT sign-in screen', () => {
  render(<App />);
  expect(screen.getByText(/sign in to your pos/i)).toBeInTheDocument();
  expect(screen.getByPlaceholderText(/username/i)).toBeInTheDocument();
});
