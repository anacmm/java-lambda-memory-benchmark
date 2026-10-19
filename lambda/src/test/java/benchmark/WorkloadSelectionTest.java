package benchmark;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.LambdaLogger;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.ArgumentCaptor;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class WorkloadSelectionTest {
    private final ObjectMapper mapper = spy(new ObjectMapper());
    private final S3DatasetReader reader = mock(S3DatasetReader.class);
    private final Calculation calculation = spy(new Calculation());
    private final Context context = mock(Context.class);
    private final LambdaLogger logger = mock(LambdaLogger.class);
    private final BenchmarkHandler handler = new BenchmarkHandler(reader, mapper, calculation);

    @BeforeEach
    void context() {
        when(context.getAwsRequestId()).thenReturn("workload-test");
        when(context.getMemoryLimitInMB()).thenReturn(1024);
        when(context.getLogger()).thenReturn(logger);
    }

    @Test
    void explicitCpuAndLegacyRequestHaveTheOriginalDatasetResult() throws Exception {
        when(reader.read("bucket", "dataset.json")).thenReturn(
                Files.readAllBytes(Path.of("../sample/dataset.json")));
        var expected = new Models.Response(4000, "b1e029a3d2d7974c", "OK");
        assertEquals(expected, handler.handleRequest(new Models.Request("cpu", "bucket", "dataset.json"), context));
        var legacy = mapper.readValue("{\"bucket\":\"bucket\",\"key\":\"dataset.json\"}", Models.Request.class);
        assertEquals(expected, handler.handleRequest(legacy, context));
        assertEquals("{\"recordsProcessed\":4000,\"checksum\":\"b1e029a3d2d7974c\",\"status\":\"OK\"}",
                mapper.writeValueAsString(expected));
        verify(calculation, times(2)).process(anyList());
        verify(reader, times(2)).read("bucket", "dataset.json");
        var logs = ArgumentCaptor.forClass(String.class);
        verify(logger, times(2)).log(logs.capture());
        for (String line : logs.getAllValues()) {
            var log = mapper.readTree(line);
            assertEquals("cpu", log.get("workload").asText());
            assertFalse(log.get("jsonMs").isNull());
            assertEquals(4000, log.get("recordsProcessed").asInt());
        }
    }

    @Test
    void ioResultIsConstantAtEveryMemorySizeAndDownloadsEachTime() throws Exception {
        when(reader.read("bucket", "dataset.json")).thenReturn(
                Files.readAllBytes(Path.of("../sample/dataset.json")));
        var request = new Models.Request("io", "bucket", "dataset.json");
        var expected = new Models.Response(null, "crc32:1c396adb", "OK", 191961L);
        int[] sizes = {256, 512, 1024, 1536, 2048, 3072};
        for (int size : sizes) {
            when(context.getMemoryLimitInMB()).thenReturn(size);
            assertEquals(expected, handler.handleRequest(request, context));
        }
        verify(reader, times(sizes.length)).read("bucket", "dataset.json");
        verifyNoInteractions(calculation);
        verify(mapper, never()).readValue(any(byte[].class), eq(Models.Dataset.class));
        var responseJson = mapper.readTree(mapper.writeValueAsBytes(expected));
        assertFalse(responseJson.has("recordsProcessed"));
        assertEquals(191961, responseJson.get("objectBytes").asInt());
        var logs = ArgumentCaptor.forClass(String.class);
        verify(logger, times(sizes.length)).log(logs.capture());
        for (int i = 0; i < sizes.length; i++) {
            var log = mapper.readTree(logs.getAllValues().get(i));
            assertEquals("io", log.get("workload").asText());
            assertEquals(i == 0, log.get("coldStart").asBoolean());
            assertEquals(sizes[i], log.get("memoryMb").asInt());
            assertEquals("OK", log.get("status").asText());
            assertEquals(expected.checksum(), log.get("checksum").asText());
            assertEquals(191961, log.get("objectBytes").asInt());
            assertTrue(log.get("recordsProcessed").isNull());
            assertTrue(log.get("jsonMs").isNull());
            assertTrue(log.get("cpuMs").asDouble() >= 0);
            assertTrue(log.get("s3Ms").asDouble() >= 0);
            assertTrue(log.get("handlerMs").asDouble() >= 0);
        }
    }

    @Test
    void ioAcceptsNonJsonWithoutCallingTheCpuCalculation() throws Exception {
        when(reader.read("bucket", "raw")).thenReturn("123456789".getBytes(StandardCharsets.US_ASCII));
        var request = mapper.readValue("{\"workload\":\"io\",\"bucket\":\"bucket\",\"key\":\"raw\"}", Models.Request.class);
        assertEquals(new Models.Response(null, "crc32:cbf43926", "OK", 9L), handler.handleRequest(request, context));
        verifyNoInteractions(calculation);
        verify(mapper, never()).readValue(any(byte[].class), eq(Models.Dataset.class));
    }

    @ParameterizedTest
    @ValueSource(strings = {"", " ", "CPU", "IO", "unknown"})
    void invalidWorkloadFailsBeforeS3AndIsLogged(String workload) throws Exception {
        assertThrows(IllegalArgumentException.class,
                () -> handler.handleRequest(new Models.Request(workload, "bucket", "key"), context));
        verifyNoInteractions(reader, calculation);
        var logs = ArgumentCaptor.forClass(String.class);
        verify(logger).log(logs.capture());
        var log = mapper.readTree(logs.getValue());
        assertEquals(workload, log.get("workload").asText());
        assertEquals("ERROR", log.get("status").asText());
    }

    @Test
    void ioS3FailureIsNotReturnedAsSuccess() throws Exception {
        when(reader.read("bucket", "key")).thenThrow(new IllegalStateException("incomplete object"));
        assertThrows(IllegalStateException.class,
                () -> handler.handleRequest(new Models.Request("io", "bucket", "key"), context));
        verifyNoInteractions(calculation);
        var logs = ArgumentCaptor.forClass(String.class);
        verify(logger).log(logs.capture());
        var log = mapper.readTree(logs.getValue());
        assertEquals("io", log.get("workload").asText());
        assertEquals("ERROR", log.get("status").asText());
        assertEquals("IllegalStateException", log.get("errorType").asText());
        assertTrue(log.get("checksum").isNull());
    }
}
