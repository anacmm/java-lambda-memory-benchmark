package benchmark;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.LambdaLogger;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class BenchmarkHandlerTest {
    private final ObjectMapper mapper = new ObjectMapper();
    private final S3DatasetReader reader = mock(S3DatasetReader.class);
    private final Context context = mock(Context.class);
    private final LambdaLogger logger = mock(LambdaLogger.class);
    private final Models.Request request = new Models.Request("bucket", "dataset.json");

    private BenchmarkHandler handler() {
        when(context.getAwsRequestId()).thenReturn("test-request");
        when(context.getMemoryLimitInMB()).thenReturn(1024);
        when(context.getLogger()).thenReturn(logger);
        return new BenchmarkHandler(reader, mapper, new Calculation());
    }

    @Test
    void sameResultAcrossMemoryAndRepeatedInvocationsWithoutObjectCaching() throws Exception {
        when(reader.read("bucket", "dataset.json")).thenReturn(
                "{\"records\":[{\"id\":1,\"value\":7919,\"category\":\"group-1\"}]}"
                        .getBytes(StandardCharsets.UTF_8));
        var handler = handler();
        var first = handler.handleRequest(request, context);
        when(context.getMemoryLimitInMB()).thenReturn(256);
        assertEquals(first, handler.handleRequest(request, context));
        verify(reader, times(2)).read("bucket", "dataset.json");
        var logs = ArgumentCaptor.forClass(String.class);
        verify(logger, times(2)).log(logs.capture());
        var cold = mapper.readTree(logs.getAllValues().get(0));
        var warm = mapper.readTree(logs.getAllValues().get(1));
        assertTrue(cold.get("coldStart").asBoolean());
        assertFalse(warm.get("coldStart").asBoolean());
        assertEquals(256, warm.get("memoryMb").asInt());
        assertEquals("OK", warm.get("status").asText());
        assertEquals(first.checksum(), warm.get("checksum").asText());
        assertTrue(warm.get("cpuMs").asDouble() >= 0);
    }

    @Test
    void invalidRequestDoesNotAccessS3() throws Exception {
        var handler = handler();
        assertThrows(IllegalArgumentException.class,
                () -> handler.handleRequest(new Models.Request("", "key"), context));
        verifyNoInteractions(reader);
        var logs = ArgumentCaptor.forClass(String.class);
        verify(logger).log(logs.capture());
        assertEquals("ERROR", mapper.readTree(logs.getValue()).get("status").asText());
    }

    @Test
    void malformedJsonAndS3ErrorsFailInvocation() {
        var handler = handler();
        when(reader.read("bucket", "dataset.json")).thenReturn("invalid".getBytes(StandardCharsets.UTF_8));
        assertThrows(IllegalArgumentException.class, () -> handler.handleRequest(request, context));
        when(reader.read("bucket", "dataset.json")).thenThrow(new IllegalStateException("S3 failed"));
        assertThrows(IllegalStateException.class, () -> handler.handleRequest(request, context));
        verify(logger, times(2)).log(anyString());
    }
}
