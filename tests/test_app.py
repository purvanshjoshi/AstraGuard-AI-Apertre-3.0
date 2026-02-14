"""
Behavior-driven tests for src/app.py - Main FastAPI Application Entry Point.

These tests validate runtime behavior, not source code structure.
All tests mock external dependencies and assert on outcomes (SystemExit, logs, calls).
"""

import pytest
import sys
import os
import signal
import logging
import runpy
from unittest.mock import patch, MagicMock
from importlib import reload


@pytest.fixture(autouse=True)
def reset_env():
    """Reset environment variables before each test."""
    original_env = os.environ.copy()
    for key in ['APP_HOST', 'APP_PORT', 'LOG_LEVEL']:
        os.environ.pop(key, None)
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_api_service():
    """Create a mock api.service module."""
    mock_app = MagicMock()
    mock_app.title = "AstraGuard AI API"
    mock_app.version = "1.0.0"
    return MagicMock(app=mock_app), mock_app


@pytest.fixture
def mock_uvicorn():
    """Create a mock uvicorn module."""
    mock_uv = MagicMock()
    mock_uv.run = MagicMock()
    return mock_uv


class TestSignalHandler:
    """Test signal_handler function behavior."""

    def test_signal_handler_logs_shutdown_message(self, mock_api_service):
        """Test that signal_handler logs shutdown message."""
        mock_service, mock_app = mock_api_service
        
        with patch.dict(sys.modules, {'api.service': mock_service}):
            if 'src.app' in sys.modules:
                del sys.modules['src.app']
            
            from src import app as app_module
            
            with patch.object(app_module.logger, 'info') as mock_log:
                with pytest.raises(SystemExit) as exc_info:
                    app_module.signal_handler(signal.SIGINT, None)
                
                mock_log.assert_called_once()
                assert 'signal' in mock_log.call_args[0][0].lower()
                assert exc_info.value.code == 0

    def test_signal_handler_exits_with_code_zero(self, mock_api_service):
        """Test that signal_handler exits gracefully with code 0."""
        mock_service, mock_app = mock_api_service
        
        with patch.dict(sys.modules, {'api.service': mock_service}):
            if 'src.app' in sys.modules:
                del sys.modules['src.app']
            
            from src import app as app_module
            
            with pytest.raises(SystemExit) as exc_info:
                app_module.signal_handler(signal.SIGTERM, None)
            
            assert exc_info.value.code == 0

    def test_signal_handler_handles_sigterm(self, mock_api_service):
        """Test signal_handler processes SIGTERM correctly."""
        mock_service, mock_app = mock_api_service
        
        with patch.dict(sys.modules, {'api.service': mock_service}):
            if 'src.app' in sys.modules:
                del sys.modules['src.app']
            
            from src import app as app_module
            
            with patch.object(app_module.logger, 'info') as mock_log:
                with pytest.raises(SystemExit):
                    app_module.signal_handler(signal.SIGTERM, MagicMock())
                
                log_message = mock_log.call_args[0][0]
                assert 'signal' in log_message.lower()


class TestAppModuleImport:
    """Test successful module import behavior."""

    def test_successful_import_exposes_app(self, mock_api_service):
        """Test that successful import exposes the app object."""
        mock_service, mock_app = mock_api_service
        
        with patch.dict(sys.modules, {'api.service': mock_service}):
            if 'src.app' in sys.modules:
                del sys.modules['src.app']
            
            from src import app as app_module
            
            assert hasattr(app_module, 'app')
            assert app_module.app is mock_app

    def test_successful_import_exposes_logger(self, mock_api_service):
        """Test that successful import exposes the logger."""
        mock_service, mock_app = mock_api_service
        
        with patch.dict(sys.modules, {'api.service': mock_service}):
            if 'src.app' in sys.modules:
                del sys.modules['src.app']
            
            from src import app as app_module
            
            assert hasattr(app_module, 'logger')
            assert isinstance(app_module.logger, logging.Logger)

    def test_successful_import_exposes_signal_handler(self, mock_api_service):
        """Test that successful import exposes signal_handler function."""
        mock_service, mock_app = mock_api_service
        
        with patch.dict(sys.modules, {'api.service': mock_service}):
            if 'src.app' in sys.modules:
                del sys.modules['src.app']
            
            from src import app as app_module
            
            assert hasattr(app_module, 'signal_handler')
            assert callable(app_module.signal_handler)


class TestMainBlockPortValidation:
    """Test port validation in main block."""

    def test_invalid_port_string_causes_exit(self, mock_api_service, mock_uvicorn):
        """Test that non-numeric APP_PORT causes sys.exit(1)."""
        mock_service, mock_app = mock_api_service
        os.environ['APP_PORT'] = 'invalid'
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')
                
                assert exc_info.value.code == 1

    def test_port_out_of_range_causes_exit(self, mock_api_service, mock_uvicorn):
        """Test that port > 65535 causes sys.exit(1)."""
        mock_service, mock_app = mock_api_service
        os.environ['APP_PORT'] = '70000'
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')
                
                assert exc_info.value.code == 1

    def test_port_zero_causes_exit(self, mock_api_service, mock_uvicorn):
        """Test that port = 0 causes sys.exit(1)."""
        mock_service, mock_app = mock_api_service
        os.environ['APP_PORT'] = '0'
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')
                
                assert exc_info.value.code == 1

    def test_negative_port_causes_exit(self, mock_api_service, mock_uvicorn):
        """Test that negative port causes sys.exit(1)."""
        mock_service, mock_app = mock_api_service
        os.environ['APP_PORT'] = '-1'
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')
                
                assert exc_info.value.code == 1


class TestMainBlockLogLevelValidation:
    """Test log level validation in main block."""

    def test_invalid_log_level_defaults_to_info(self, mock_api_service, mock_uvicorn):
        """Test that invalid LOG_LEVEL defaults to 'info' without exiting."""
        mock_service, mock_app = mock_api_service
        os.environ['LOG_LEVEL'] = 'invalid_level'
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')
                
                mock_uvicorn.run.assert_called_once()
                call_kwargs = mock_uvicorn.run.call_args[1]
                assert call_kwargs['log_level'] == 'info'

    def test_valid_log_level_debug_is_accepted(self, mock_api_service, mock_uvicorn):
        """Test that LOG_LEVEL='debug' is accepted."""
        mock_service, mock_app = mock_api_service
        os.environ['LOG_LEVEL'] = 'DEBUG'
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')
                
                call_kwargs = mock_uvicorn.run.call_args[1]
                assert call_kwargs['log_level'] == 'debug'

    def test_valid_log_level_error_is_accepted(self, mock_api_service, mock_uvicorn):
        """Test that LOG_LEVEL='error' is accepted."""
        mock_service, mock_app = mock_api_service
        os.environ['LOG_LEVEL'] = 'error'
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')
                
                call_kwargs = mock_uvicorn.run.call_args[1]
                assert call_kwargs['log_level'] == 'error'


class TestMainBlockUvicornConfiguration:
    """Test uvicorn.run configuration in main block."""

    def test_uvicorn_run_called_with_default_host(self, mock_api_service, mock_uvicorn):
        """Test uvicorn.run is called with default host 0.0.0.0."""
        mock_service, mock_app = mock_api_service
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')
                
                call_kwargs = mock_uvicorn.run.call_args[1]
                assert call_kwargs['host'] == '0.0.0.0'

    def test_uvicorn_run_called_with_default_port(self, mock_api_service, mock_uvicorn):
        """Test uvicorn.run is called with default port 8002."""
        mock_service, mock_app = mock_api_service
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')
                
                call_kwargs = mock_uvicorn.run.call_args[1]
                assert call_kwargs['port'] == 8002

    def test_uvicorn_run_uses_custom_host_from_env(self, mock_api_service, mock_uvicorn):
        """Test uvicorn.run uses APP_HOST from environment."""
        mock_service, mock_app = mock_api_service
        os.environ['APP_HOST'] = '127.0.0.1'
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')
                
                call_kwargs = mock_uvicorn.run.call_args[1]
                assert call_kwargs['host'] == '127.0.0.1'

    def test_uvicorn_run_uses_custom_port_from_env(self, mock_api_service, mock_uvicorn):
        """Test uvicorn.run uses APP_PORT from environment."""
        mock_service, mock_app = mock_api_service
        os.environ['APP_PORT'] = '9000'
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')
                
                call_kwargs = mock_uvicorn.run.call_args[1]
                assert call_kwargs['port'] == 9000

    def test_uvicorn_run_receives_app_instance(self, mock_api_service, mock_uvicorn):
        """Test uvicorn.run receives the app instance."""
        mock_service, mock_app = mock_api_service
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')
                
                call_args = mock_uvicorn.run.call_args[0]
                assert call_args[0] is mock_app


class TestMainBlockErrorHandling:
    """Test error handling in main block."""

    def test_uvicorn_import_error_causes_exit(self, mock_api_service):
        """Test that uvicorn ImportError causes sys.exit(1)."""
        mock_service, mock_app = mock_api_service
        
        # Make uvicorn import fail
        if 'uvicorn' in sys.modules:
            del sys.modules['uvicorn']
        
        with patch.dict(sys.modules, {'api.service': mock_service}):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')
                
                assert exc_info.value.code == 1

    def test_oserror_address_in_use_causes_exit(self, mock_api_service, mock_uvicorn):
        """Test that OSError (address in use) causes sys.exit(1)."""
        mock_service, mock_app = mock_api_service
        
        os_error = OSError("Address already in use")
        os_error.errno = 98  # EADDRINUSE on Linux
        mock_uvicorn.run.side_effect = os_error
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')
                
                assert exc_info.value.code == 1

    def test_oserror_permission_denied_causes_exit(self, mock_api_service, mock_uvicorn):
        """Test that OSError (permission denied) causes sys.exit(1)."""
        mock_service, mock_app = mock_api_service
        
        os_error = OSError("Permission denied")
        os_error.errno = 13  # EACCES
        mock_uvicorn.run.side_effect = os_error
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')
                
                assert exc_info.value.code == 1

    def test_oserror_other_causes_exit(self, mock_api_service, mock_uvicorn):
        """Test that other OSError causes sys.exit(1)."""
        mock_service, mock_app = mock_api_service
        
        os_error = OSError("Some other error")
        os_error.errno = 999
        mock_uvicorn.run.side_effect = os_error
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')
                
                assert exc_info.value.code == 1

    def test_keyboard_interrupt_causes_graceful_exit(self, mock_api_service, mock_uvicorn):
        """Test that KeyboardInterrupt causes sys.exit(0)."""
        mock_service, mock_app = mock_api_service
        mock_uvicorn.run.side_effect = KeyboardInterrupt()
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')
                
                assert exc_info.value.code == 0

    def test_unexpected_exception_causes_exit(self, mock_api_service, mock_uvicorn):
        """Test that unexpected Exception causes sys.exit(1)."""
        mock_service, mock_app = mock_api_service
        mock_uvicorn.run.side_effect = RuntimeError("Unexpected error")
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')
                
                assert exc_info.value.code == 1


class TestMainBlockSignalRegistration:
    """Test signal handler registration in main block."""

    def test_sigint_handler_is_registered(self, mock_api_service, mock_uvicorn):
        """Test that SIGINT handler is registered."""
        mock_service, mock_app = mock_api_service
        mock_signal_func = MagicMock()
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal', mock_signal_func):
                runpy.run_path('src/app.py', run_name='__main__')
                
                sigint_calls = [c for c in mock_signal_func.call_args_list 
                               if c[0][0] == signal.SIGINT]
                assert len(sigint_calls) >= 1

    def test_sigterm_handler_is_registered(self, mock_api_service, mock_uvicorn):
        """Test that SIGTERM handler is registered."""
        mock_service, mock_app = mock_api_service
        mock_signal_func = MagicMock()
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal', mock_signal_func):
                runpy.run_path('src/app.py', run_name='__main__')
                
                sigterm_calls = [c for c in mock_signal_func.call_args_list 
                                if c[0][0] == signal.SIGTERM]
                assert len(sigterm_calls) >= 1


class TestMainBlockLogging:
    """Test logging behavior in main block."""

    def test_startup_logs_host_and_port(self, mock_api_service, mock_uvicorn):
        """Test that startup logs host and port."""
        mock_service, mock_app = mock_api_service
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                with patch('logging.Logger.info') as mock_log:
                    runpy.run_path('src/app.py', run_name='__main__')
                    
                    all_log_messages = ' '.join(str(c) for c in mock_log.call_args_list)
                    assert '0.0.0.0' in all_log_messages or 'host' in all_log_messages.lower()

    def test_error_logs_on_invalid_port(self, mock_api_service, mock_uvicorn):
        """Test that error is logged on invalid port."""
        mock_service, mock_app = mock_api_service
        os.environ['APP_PORT'] = 'not_a_number'
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                with patch('logging.Logger.error') as mock_error:
                    with pytest.raises(SystemExit):
                        runpy.run_path('src/app.py', run_name='__main__')
                    
                    assert mock_error.called

    def test_warning_logged_for_invalid_log_level(self, mock_api_service, mock_uvicorn):
        """Test that warning is logged for invalid log level."""
        mock_service, mock_app = mock_api_service
        os.environ['LOG_LEVEL'] = 'banana'
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                with patch('logging.Logger.warning') as mock_warning:
                    runpy.run_path('src/app.py', run_name='__main__')
                    
                    assert mock_warning.called


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_port_1_is_valid(self, mock_api_service, mock_uvicorn):
        """Test that port 1 is accepted (boundary)."""
        mock_service, mock_app = mock_api_service
        os.environ['APP_PORT'] = '1'
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')
                
                call_kwargs = mock_uvicorn.run.call_args[1]
                assert call_kwargs['port'] == 1

    def test_port_65535_is_valid(self, mock_api_service, mock_uvicorn):
        """Test that port 65535 is accepted (boundary)."""
        mock_service, mock_app = mock_api_service
        os.environ['APP_PORT'] = '65535'
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')
                
                call_kwargs = mock_uvicorn.run.call_args[1]
                assert call_kwargs['port'] == 65535

    def test_port_65536_is_invalid(self, mock_api_service, mock_uvicorn):
        """Test that port 65536 is rejected (boundary)."""
        mock_service, mock_app = mock_api_service
        os.environ['APP_PORT'] = '65536'
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')
                
                assert exc_info.value.code == 1

    def test_all_valid_log_levels(self, mock_api_service, mock_uvicorn):
        """Test all valid log levels are accepted."""
        valid_levels = ["critical", "error", "warning", "info", "debug"]
        mock_service, mock_app = mock_api_service
        
        for level in valid_levels:
            mock_uvicorn.run.reset_mock()
            os.environ['LOG_LEVEL'] = level
            
            with patch.dict(sys.modules, {
                'api.service': mock_service,
                'uvicorn': mock_uvicorn
            }):
                with patch('signal.signal'):
                    runpy.run_path('src/app.py', run_name='__main__')
                    
                    call_kwargs = mock_uvicorn.run.call_args[1]
                    assert call_kwargs['log_level'] == level

    def test_log_level_case_insensitive(self, mock_api_service, mock_uvicorn):
        """Test that log level is case insensitive."""
        mock_service, mock_app = mock_api_service
        os.environ['LOG_LEVEL'] = 'WARNING'
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')
                
                call_kwargs = mock_uvicorn.run.call_args[1]
                assert call_kwargs['log_level'] == 'warning'


class TestOSErrorSpecificCodes:
    """Test specific OSError errno handling."""

    def test_oserror_errno_48_address_in_use_mac(self, mock_api_service, mock_uvicorn):
        """Test OSError with errno 48 (address in use on macOS)."""
        mock_service, mock_app = mock_api_service
        
        os_error = OSError("Address already in use")
        os_error.errno = 48  # EADDRINUSE on macOS
        mock_uvicorn.run.side_effect = os_error
        
        with patch.dict(sys.modules, {
            'api.service': mock_service,
            'uvicorn': mock_uvicorn
        }):
            with patch('signal.signal'):
                with patch('logging.Logger.error') as mock_error:
                    with pytest.raises(SystemExit) as exc_info:
                        runpy.run_path('src/app.py', run_name='__main__')
                    
                    assert exc_info.value.code == 1
                    assert mock_error.called
