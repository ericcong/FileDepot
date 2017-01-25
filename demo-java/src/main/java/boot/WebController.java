package boot;

import org.springframework.web.bind.annotation.*;
import org.springframework.beans.factory.annotation.*;
import org.springframework.stereotype.*;
import org.springframework.ui.*;

import org.springframework.web.servlet.view.*;

import javax.servlet.http.*;
import org.springframework.http.*;
import org.springframework.web.client.*;
import org.springframework.boot.json.*;

import java.util.*;

import org.slf4j.*;

@CrossOrigin(origins="*")
@Controller
public class WebController {

    private static final Logger log = LoggerFactory.getLogger(WebController.class);

    @RequestMapping(value="/viewfile", method=RequestMethod.GET)
    public RedirectView view(
    	@RequestParam(value="id", required=true) String id
    ) {
        return new RedirectView("http://www.google.com");
    }

    @RequestMapping(value="/uploadfile", method=RequestMethod.POST)
    public ResponseEntity<String> upload(
        @RequestBody String body
    ) {
        String locker = reserve(login());
        log.info(locker);
        HttpHeaders responseHeaders = new HttpHeaders();
        responseHeaders.setContentType(MediaType.APPLICATION_JSON);
        return new ResponseEntity<String>(locker, 
            responseHeaders, HttpStatus.OK);
    }

    private String login() {
        RestTemplate restTemplate = new RestTemplate();
        ResponseEntity<String> response = restTemplate.postForEntity(
            "http://lowcost-env.rsgwu3uhma.us-east-1.elasticbeanstalk.com/login", 
            "{ \"type\": \"CAS\", \"cred\": { \"id\": \"test\" } }",
            String.class);
        Map<String, Object> m = JsonParserFactory.getJsonParser()
            .parseMap(response.getBody());
        return m.get("session_id").toString();        
    }

    private String reserve(String sessionId) {
        RestTemplate restTemplate = new RestTemplate();
        ResponseEntity<String> response = restTemplate.postForEntity(
            "http://lowcost-env.rsgwu3uhma.us-east-1.elasticbeanstalk.com/lockers", 
            "{ \"session_id\": \""+ sessionId +"\", "+
            "\"packages\": [{}] }",
            String.class);
        return response.getBody();
    }
}
